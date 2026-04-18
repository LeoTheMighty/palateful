import UIKit
import SwiftUI
import Social

/// The extension entry point. iOS instantiates this via the
/// NSExtensionPrincipalClass key in Info.plist whenever the user taps
/// Palateful in a share sheet.
///
/// Responsibilities, in order:
///   1. Read SharedContext from the App Group (auth + books). Degrade to a
///      "sign in" layout if missing.
///   2. Host ShareView with a ShareViewModel. Feed the extension's
///      NSExtensionItem attachments into the view model.
///   3. On Save: persist the pending_imports record, kick off the
///      background URLSession upload, and call completeRequest within
///      100ms. The OS takes over once completeRequest returns.
@objc(ShareViewController)
class ShareViewController: UIViewController {
  private var viewModel: ShareViewModel?
  private var uploadService: UploadService?

  override func viewDidLoad() {
    super.viewDidLoad()
    view.backgroundColor = .clear

    let context = SharedState.read()
    let viewModel = ShareViewModel(context: context)
    self.viewModel = viewModel

    if let context {
      self.uploadService = UploadService(
        sessionIdentifier: viewModel.uploadSessionIdentifier,
        context: context
      )
    }

    // Parse the extension attachments before first render so the sheet
    // can skip the "Reading content…" spinner when iOS has already handed
    // us the item synchronously.
    let items = (extensionContext?.inputItems as? [NSExtensionItem]) ?? []
    viewModel.startDetection(items: items)

    let hostingController = UIHostingController(
      rootView: ShareView(
        viewModel: viewModel,
        onSave: { [weak self] in self?.saveAndDismiss() },
        onCancel: { [weak self] in self?.cancelAndDismiss() },
        onClose: { [weak self] in self?.cancelAndDismiss() }
      )
    )
    addChild(hostingController)
    hostingController.view.translatesAutoresizingMaskIntoConstraints = false
    hostingController.view.backgroundColor = .clear
    view.addSubview(hostingController.view)
    NSLayoutConstraint.activate([
      hostingController.view.topAnchor.constraint(equalTo: view.topAnchor),
      hostingController.view.bottomAnchor.constraint(equalTo: view.bottomAnchor),
      hostingController.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
      hostingController.view.trailingAnchor.constraint(equalTo: view.trailingAnchor)
    ])
    hostingController.didMove(toParent: self)
  }

  override func viewDidLayoutSubviews() {
    super.viewDidLayoutSubviews()
    // iPad popover fix (sie-5): match the intrinsic height of the sheet
    // so the system doesn't stretch it to full screen. preferredContentSize
    // is the canonical way to tell UIPresentationController "this is how
    // big I want to be" in popover / form-sheet presentations.
    preferredContentSize = CGSize(width: 340, height: 300)
  }

  // MARK: - Save / Cancel

  private func saveAndDismiss() {
    guard let viewModel else {
      dismissExtension()
      return
    }

    Task { @MainActor in
      // Capture fileURL before save() flips state to .saved.
      let fileURL: URL?
      if case .readyFile(let url, _, _) = viewModel.state {
        fileURL = url
      } else {
        fileURL = nil
      }

      guard let record = viewModel.save() else {
        return
      }

      // Hand off to the background / ephemeral sessions BEFORE dismiss —
      // the file-upload path needs the fileURL which only lives inside
      // the extension sandbox. For URL / text shares the record contains
      // everything the reconciler needs, so .start(record:) is sufficient
      // even if the extension is reaped before the /import POST lands.
      if let fileURL {
        uploadService?.startFileUpload(record: record, fileURL: fileURL)
      } else {
        uploadService?.start(record: record)
      }

      // Dismiss within 100ms of save() returning. If the system kills us
      // before the network call lands, the main-app reconciler retries
      // URL / text shares on next foreground (file shares are lost per
      // the v1 limitation noted in SHARE.md).
      self.dismissExtension()
    }
  }

  private func cancelAndDismiss() {
    viewModel?.markCancelled()
    dismissExtension()
  }

  private func dismissExtension() {
    extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
  }
}
