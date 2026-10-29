/* Keep document geometry stable while Safari pans/resizes its visual viewport.
 * Only the application shell moves; conversation scroll positions are untouched.
 */
(function (root) {
  "use strict";

  function install(win, doc) {
    let frame = null;
    let watchUntil = 0;
    let lastHeight;
    let lastTop;
    const viewport = win.visualViewport;
    const now = () => win.performance?.now() ?? Date.now();
    function update() {
      // A pinch zoom should magnify the page, not reflow the application.
      if (viewport && Math.abs(viewport.scale - 1) > 0.01) return;
      const height = viewport?.height || win.innerHeight;
      const top = Math.max(0, viewport?.offsetTop || 0);
      if (!Number.isFinite(height) || height <= 0) return;
      if (height !== lastHeight) {
        lastHeight = height;
        doc.documentElement.style.setProperty("--app-height", `${height}px`);
      }
      if (top !== lastTop) {
        lastTop = top;
        doc.documentElement.style.setProperty("--app-top", `${top}px`);
      }
    }
    function tick() {
      frame = null;
      update();
      if (now() < watchUntil && !doc.hidden) frame = win.requestAnimationFrame(tick);
    }
    function watch() {
      update();
      if (!viewport || doc.hidden || Math.abs(viewport.scale - 1) > 0.01) return;
      // Safari may change geometry between its viewport events. Observe only
      // the short keyboard transition; there is no polling while idle/playing.
      watchUntil = now() + 500;
      if (frame === null) frame = win.requestAnimationFrame(tick);
    }
    function focusChanged(event) {
      const field = event.target;
      const textInput = field?.tagName === "INPUT" &&
        ["", "text", "search", "email", "url", "tel", "number", "password"].includes(field.type || "");
      if (field?.tagName === "TEXTAREA" || textInput || field?.isContentEditable) watch();
    }
    function cancelWatch() {
      watchUntil = 0;
      if (frame !== null) win.cancelAnimationFrame(frame);
      frame = null;
    }
    function visibilityChanged() {
      if (doc.hidden) cancelWatch();
      else update();
    }
    const targets = [[win, "resize", watch], [win, "pageshow", update],
      [doc, "focusin", focusChanged], [doc, "focusout", focusChanged],
      [doc, "visibilitychange", visibilityChanged]];
    if (viewport) targets.push([viewport, "resize", watch], [viewport, "scroll", update]);
    // Apply published geometry in the event itself, without waiting another
    // frame for the application to catch up with a native keyboard pan.
    for (const [target, name, handler] of targets) target.addEventListener(name, handler);
    update();
    return () => {
      cancelWatch();
      for (const [target, name, handler] of targets) target.removeEventListener(name, handler);
    };
  }

  function focusInput(input, win = root) {
    // Touch users choose when to open the keyboard. A completed request, map
    // change or modal dismissal must not summon it or pan the page again.
    if (win.matchMedia?.("(hover: hover) and (pointer: fine)").matches) {
      input.focus({preventScroll: true});
    }
  }

  root.KronoViewport = {install, focusInput};
  if (typeof module !== "undefined") module.exports = root.KronoViewport;
})(typeof window !== "undefined" ? window : globalThis);
