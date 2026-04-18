#!/usr/bin/env ruby
# frozen_string_literal: true

# Idempotent script that wires the PalatefulShare Share Extension target
# into Runner.xcodeproj.
#
# Why this exists: adding an Xcode target by hand-editing project.pbxproj is
# bug-prone. Running this with the xcodeproj Ruby gem (shipped with CocoaPods
# and also available standalone) gives us a safe, re-runnable pathway.
#
# Usage: ruby app/ios/scripts/add_share_extension.rb
# Dependencies: `gem install xcodeproj` (usually already present via CocoaPods).

require "xcodeproj"

REPO_ROOT = File.expand_path("../../../..", __FILE__)
PROJECT_PATH = File.join(REPO_ROOT, "app/ios/Runner.xcodeproj")
TARGET_NAME = "PalatefulShare"
BUNDLE_ID = "com.palateful.palateful.share"
TEAM_ID = "H66YP2QFW2"
DEPLOYMENT_TARGET = "14.0" # SwiftUI + Menu + ProgressView require 14+
APP_GROUP = "group.com.palateful.app"

SOURCE_FILES = %w[
  ShareViewController.swift
  ShareView.swift
  ShareViewModel.swift
  SharedState.swift
  UploadService.swift
  PendingImports.swift
  Telemetry.swift
].freeze

project = Xcodeproj::Project.open(PROJECT_PATH)

runner_target = project.targets.find { |t| t.name == "Runner" } or
  abort("Runner target not found — aborting.")

existing = project.targets.find { |t| t.name == TARGET_NAME }
if existing
  puts "Target #{TARGET_NAME} already exists; syncing file refs only."
  target = existing
else
  puts "Creating #{TARGET_NAME} target."
  target = project.new_target(
    :app_extension,
    TARGET_NAME,
    :ios,
    DEPLOYMENT_TARGET
  )
end

# Target group (virtual folder in the Xcode navigator).
group = project.main_group.find_subpath(TARGET_NAME, true)
group.set_source_tree("<group>")
group.set_path(TARGET_NAME)

# Resolve the source-tree path for the target directory.
target_dir = File.join(File.dirname(PROJECT_PATH), TARGET_NAME)

# Track files we want in the target so we can stop re-adding them.
existing_source_paths = target.source_build_phase.files
  .map(&:file_ref)
  .compact
  .map(&:real_path)
  .map(&:to_s)

SOURCE_FILES.each do |filename|
  abs = File.join(target_dir, filename)
  next unless File.exist?(abs)
  next if existing_source_paths.include?(abs)

  ref = group.files.find { |f| f.path == filename } || group.new_reference(filename)
  target.source_build_phase.add_file_reference(ref, true)
end

# Info.plist + entitlements (non-compiled resources, but referenced in build
# settings, not as a resources phase entry — standard pattern).
%w[Info.plist PalatefulShare.entitlements].each do |filename|
  abs = File.join(target_dir, filename)
  next unless File.exist?(abs)
  next if group.files.any? { |f| f.path == filename }
  group.new_reference(filename)
end

# Build settings (apply to every configuration: Debug, Release, Profile).
target.build_configurations.each do |config|
  bs = config.build_settings
  bs["PRODUCT_BUNDLE_IDENTIFIER"] = BUNDLE_ID
  bs["PRODUCT_NAME"] = "$(TARGET_NAME)"
  bs["IPHONEOS_DEPLOYMENT_TARGET"] = DEPLOYMENT_TARGET
  bs["INFOPLIST_FILE"] = "#{TARGET_NAME}/Info.plist"
  bs["CODE_SIGN_ENTITLEMENTS"] = "#{TARGET_NAME}/#{TARGET_NAME}.entitlements"
  bs["CODE_SIGN_STYLE"] = "Automatic"
  bs["DEVELOPMENT_TEAM"] = TEAM_ID
  bs["SWIFT_VERSION"] = "5.0"
  bs["TARGETED_DEVICE_FAMILY"] = "1,2"
  bs["CURRENT_PROJECT_VERSION"] = "$(FLUTTER_BUILD_NUMBER)"
  bs["MARKETING_VERSION"] = "$(FLUTTER_BUILD_NAME)"
  bs["LD_RUNPATH_SEARCH_PATHS"] = [
    "$(inherited)",
    "@executable_path/Frameworks",
    "@executable_path/../../Frameworks"
  ]
  bs["SKIP_INSTALL"] = "YES"
  bs["ASSETCATALOG_COMPILER_APPICON_NAME"] = "AppIcon"
  bs["GENERATE_INFOPLIST_FILE"] = "NO"
end

# Ensure the Runner target depends on the extension and embeds it.
existing_dep = runner_target.dependencies.any? { |d| d.target == target }
runner_target.add_dependency(target) unless existing_dep

embed_phase_name = "Embed App Extensions"
embed_phase = runner_target.copy_files_build_phases.find do |p|
  p.name == embed_phase_name || p.symbol_dst_subfolder_spec == :plug_ins
end

unless embed_phase
  embed_phase = runner_target.new_copy_files_build_phase(embed_phase_name)
  embed_phase.symbol_dst_subfolder_spec = :plug_ins
  embed_phase.run_only_for_deployment_postprocessing = "0"
  # Rearrange phases: the embed phase must run AFTER "Thin Binary" /
  # frameworks copy so the appex is present in the wrapper before
  # codesign. Xcode typically adds it near the end by default; xcodeproj
  # appends at the end, which is the right place.
end

appex_ref = target.product_reference
if embed_phase.files_references.none? { |r| r == appex_ref }
  build_file = embed_phase.add_file_reference(appex_ref, true)
  build_file.settings = { "ATTRIBUTES" => ["RemoveHeadersOnCopy"] }
end

project.save
puts "Saved #{PROJECT_PATH} — #{TARGET_NAME} target is wired in."
