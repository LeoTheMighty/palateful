import UIKit
import SwiftUI
import Social

@objc(ShareViewController)
class ShareViewController: UIViewController {
  override func viewDidLoad() {
    super.viewDidLoad()
    view.backgroundColor = .clear

    let hostingController = UIHostingController(
      rootView: PlaceholderShareView(
        onClose: { [weak self] in self?.dismissExtension() }
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

  private func dismissExtension() {
    extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
  }
}

private struct PlaceholderShareView: View {
  let onClose: () -> Void

  var body: some View {
    VStack(spacing: 16) {
      Spacer()
      Text("Save to Palateful")
        .font(.headline)
      Text("Extension wired up — implementation arriving in sie-2 / sie-3.")
        .font(.footnote)
        .foregroundColor(.secondary)
        .multilineTextAlignment(.center)
        .padding(.horizontal, 24)
      Button("Close", action: onClose)
        .padding(.top, 8)
      Spacer()
    }
    .frame(maxWidth: .infinity, maxHeight: .infinity)
    .background(Color(.systemBackground))
  }
}
