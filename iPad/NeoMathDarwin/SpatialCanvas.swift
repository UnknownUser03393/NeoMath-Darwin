import SwiftUI
import UIKit

struct SpatialCanvas<Content: View>: UIViewRepresentable {
    var world: CGSize
    @Binding var zoom: CGFloat
    @Binding var viewport: CGPoint
    var fitRequest: Int
    var fitBounds: CGSize
    var drawingWithFinger = false
    @ViewBuilder var content: () -> Content
    func makeCoordinator() -> Coordinator { Coordinator(self) }
    func makeUIView(context: Context) -> UIScrollView {
        let view = UIScrollView()
        view.minimumZoomScale = 0.25
        view.maximumZoomScale = 4
        view.bouncesZoom = true
        view.showsHorizontalScrollIndicator = false
        view.showsVerticalScrollIndicator = false
        view.backgroundColor = UIColor(DarwinTheme.canvas)
        view.delaysContentTouches = false
        view.canCancelContentTouches = !drawingWithFinger
        view.delegate = context.coordinator
        view.panGestureRecognizer.minimumNumberOfTouches = drawingWithFinger ? 2 : 1
        let hosting = UIHostingController(rootView: content())
        hosting.view.backgroundColor = .clear
        hosting.view.frame = CGRect(origin: .zero, size: world)
        view.addSubview(hosting.view)
        view.contentSize = world
        context.coordinator.hosting = hosting
        view.setZoomScale(zoom, animated: false)
        view.setContentOffset(viewport, animated: false)
        return view
    }
    func updateUIView(_ view: UIScrollView, context: Context) {
        let c = context.coordinator
        c.parent = self
        view.canCancelContentTouches = !drawingWithFinger
        view.panGestureRecognizer.minimumNumberOfTouches = drawingWithFinger ? 2 : 1
        c.hosting?.rootView = content()
        if c.world != world {
            c.hosting?.view.bounds.size = world
            view.contentSize = CGSize(width: world.width * view.zoomScale, height: world.height * view.zoomScale)
            c.world = world
        }
        if c.fitRequest != fitRequest, view.bounds.width > 0 {
            c.fitRequest = fitRequest
            let scale = max(0.25, min(4, min((view.bounds.width - 48) / fitBounds.width, (view.bounds.height - 160) / fitBounds.height)))
            c.positioning = true
            view.setZoomScale(scale, animated: false)
            view.setContentOffset(.zero, animated: false)
            c.positioning = false
            DispatchQueue.main.async { zoom = scale; viewport = .zero }
        } else if abs(view.zoomScale - zoom) > 0.001 && !view.isZooming {
            let center = CGPoint(x: (view.contentOffset.x + view.bounds.width/2) / view.zoomScale, y: (view.contentOffset.y + view.bounds.height/2) / view.zoomScale)
            view.setZoomScale(zoom, animated: false)
            view.contentOffset = CGPoint(x: max(0, center.x * zoom - view.bounds.width/2), y: max(0, center.y * zoom - view.bounds.height/2))
        }
    }
    final class Coordinator: NSObject, UIScrollViewDelegate {
        var parent: SpatialCanvas
        var hosting: UIHostingController<Content>?
        var world: CGSize
        var fitRequest: Int
        var positioning = false
        init(_ parent: SpatialCanvas) { self.parent = parent; world = parent.world; fitRequest = parent.fitRequest }
        func viewForZooming(in scrollView: UIScrollView) -> UIView? { hosting?.view }
        // UIKit owns every frame of dragging, deceleration and pinching. Publishing
        // each frame would rebuild the hosted document and re-layout its formulas.
        private func publishPosition(_ scrollView: UIScrollView) {
            guard !positioning else { return }
            let offset = scrollView.contentOffset
            let scale = scrollView.zoomScale
            DispatchQueue.main.async { [weak self] in
                guard let self else { return }
                if parent.viewport != offset { parent.viewport = offset }
                if abs(parent.zoom - scale) > 0.001 { parent.zoom = scale }
            }
        }
        func scrollViewDidEndDragging(_ scrollView: UIScrollView, willDecelerate decelerate: Bool) {
            if !decelerate { publishPosition(scrollView) }
        }
        func scrollViewDidEndDecelerating(_ scrollView: UIScrollView) { publishPosition(scrollView) }
        func scrollViewDidEndZooming(_ scrollView: UIScrollView, with view: UIView?, atScale scale: CGFloat) { publishPosition(scrollView) }
    }
}
