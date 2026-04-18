import SwiftUI

/// The 300-px confirmation sheet. Minimal: icon + title + summary + book
/// picker + Save/Cancel. Every error state has its own layout driven
/// entirely by ShareViewModel.state so a reader can grep for ShareState
/// cases to find every possible UI variant.
struct ShareView: View {
  @ObservedObject var viewModel: ShareViewModel
  let onSave: () -> Void
  let onCancel: () -> Void
  let onClose: () -> Void

  var body: some View {
    VStack(spacing: 0) {
      header
      Divider()
      body(for: viewModel.state)
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 16)
        .padding(.vertical, 20)
      Divider()
      footer(for: viewModel.state)
    }
    .background(Color(.systemBackground))
    .accessibilityElement(children: .contain)
    .onAppear {
      UIAccessibility.post(
        notification: .screenChanged,
        argument: "Save to Palateful"
      )
    }
  }

  // MARK: - Sections

  private var header: some View {
    HStack(spacing: 10) {
      Image(systemName: "fork.knife")
        .font(.title2)
        .foregroundColor(.accentColor)
        .accessibilityHidden(true)
      Text("Save to Palateful")
        .font(.headline)
        .dynamicTypeSize(.medium ... .accessibility2)
        .accessibilityAddTraits(.isHeader)
      Spacer()
    }
    .padding(.horizontal, 16)
    .padding(.vertical, 14)
  }

  @ViewBuilder
  private func body(for state: ShareState) -> some View {
    switch state {
    case .detecting:
      ProgressView("Reading content…")
        .dynamicTypeSize(.medium ... .accessibility2)
    case .needsSignIn:
      infoBlock(
        title: "Sign in to save shared recipes",
        detail: "Open Palateful and sign in, then try sharing again."
      )
    case .jwtNearExpiry:
      infoBlock(
        title: "Refresh sign-in to save",
        detail: "Open Palateful to refresh sign-in."
      )
    case .unsupportedType:
      infoBlock(
        title: "Palateful can't read this type yet",
        detail: "Try sharing a URL, PDF, image, or video instead."
      )
    case .oversized(let bytes):
      infoBlock(
        title: "This file is too large",
        detail: "\(formatBytes(bytes)) is above the 100 MB share cap. Open Palateful and import it from Files."
      )
    case .readyUrl(let url):
      readyContent(summary: "Recipe URL · \(url.host ?? url.absoluteString)")
    case .readyText(let text):
      readyContent(summary: "Recipe text · \(text.prefix(40))…")
    case .readyFile(_, let bytes, let mime):
      readyContent(summary: "\(formatLabel(mime: mime)) · \(formatBytes(bytes))")
    case .saving:
      ProgressView("Saving…")
    case .saved:
      Label("Saved", systemImage: "checkmark.circle.fill")
        .font(.title3)
        .foregroundColor(.green)
    case .failed(let code, let id):
      infoBlock(
        title: "Couldn't save",
        detail: ShareErrorCopy.message(for: code, errorId: id)
      )
    }
  }

  @ViewBuilder
  private func footer(for state: ShareState) -> some View {
    switch state {
    case .detecting, .saving, .saved:
      HStack {
        Button("Cancel", action: onCancel)
          .accessibilityHint("Dismiss without saving")
        Spacer()
      }
      .padding()
    case .needsSignIn, .jwtNearExpiry, .unsupportedType, .oversized, .failed:
      HStack {
        Spacer()
        Button("Close", action: onClose)
          .buttonStyle(.borderedProminent)
      }
      .padding()
    case .readyUrl, .readyText, .readyFile:
      HStack {
        Button("Cancel", action: onCancel)
        Spacer()
        Button("Save", action: onSave)
          .buttonStyle(.borderedProminent)
          .disabled(viewModel.selectedBookId == nil)
      }
      .padding()
    }
  }

  // MARK: - Building blocks

  @ViewBuilder
  private func readyContent(summary: String) -> some View {
    VStack(alignment: .leading, spacing: 12) {
      if viewModel.multiItemTruncated > 0 {
        Text("Only the first of \(viewModel.multiItemTruncated + 1) items will be saved.")
          .font(.footnote)
          .foregroundColor(.orange)
          .accessibilityAddTraits(.isHeader)
      }
      Text(summary)
        .font(.subheadline)
        .lineLimit(2)
        .foregroundColor(.primary)
      if !viewModel.availableBooks.isEmpty {
        Menu {
          ForEach(viewModel.availableBooks, id: \.id) { book in
            Button(book.name) {
              viewModel.selectedBookId = book.id
            }
          }
        } label: {
          HStack {
            Text("Save to")
              .foregroundColor(.secondary)
            Text(selectedBookLabel)
              .foregroundColor(.accentColor)
            Image(systemName: "chevron.down")
              .foregroundColor(.secondary)
              .font(.footnote)
          }
          .frame(maxWidth: .infinity, alignment: .leading)
        }
        .accessibilityLabel("Select recipe book")
      }
      if case .readyFile(_, let bytes, _) = viewModel.state,
         bytes > ShareViewModel.disclosureBytesThreshold {
        Text("Uploading \(formatBytes(bytes)) to Palateful")
          .font(.caption)
          .foregroundColor(.secondary)
      }
    }
  }

  @ViewBuilder
  private func infoBlock(title: String, detail: String) -> some View {
    VStack(alignment: .leading, spacing: 8) {
      Text(title)
        .font(.subheadline)
        .fontWeight(.semibold)
      Text(detail)
        .font(.footnote)
        .foregroundColor(.secondary)
    }
  }

  private var selectedBookLabel: String {
    let id = viewModel.selectedBookId
    return viewModel.availableBooks.first(where: { $0.id == id })?.name ?? "Choose book"
  }

  private func formatBytes(_ bytes: Int64) -> String {
    let fmt = ByteCountFormatter()
    fmt.allowedUnits = [.useMB, .useKB]
    fmt.countStyle = .file
    return fmt.string(fromByteCount: bytes)
  }

  private func formatLabel(mime: String) -> String {
    if mime == "application/pdf" { return "Recipe PDF" }
    if mime.hasPrefix("image/") { return "Recipe photo" }
    if mime.hasPrefix("video/") { return "Recipe video" }
    if mime.hasPrefix("audio/") { return "Recipe audio" }
    return "Recipe file"
  }
}
