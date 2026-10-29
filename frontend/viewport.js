/* Keep document geometry stable while Safari pans/resizes its visual viewport.
 * Only the application shell moves; conversation scroll positions are untouched.
 */
(function (root) {
  "use strict";

  function install(win, doc) {
    let frame = null;
    let last = "";
    const viewport = win.visualViewport;
    function update() {
      frame = null;
      // A pinch zoom should magnify the page, not reflow the application.
      if (viewport && Math.abs(viewport.scale - 1) > 0.01) return;
      const height = viewport?.height || win.innerHeight;
      const top = Math.max(0, viewport?.offsetTop || 0);
      if (!Number.isFinite(height) || height <= 0) return;
      const geometry = `${height}:${top}`;
      if (geometry === last) return;
      last = geometry;
      doc.documentElement.style.setProperty("--app-height", `${height}px`);
      doc.documentElement.style.setProperty("--app-top", `${top}px`);
    }
    function schedule() {
      if (frame === null) frame = win.requestAnimationFrame(update);
    }
    const targets = [[win, "resize"], [win, "pageshow"]];
    if (viewport) targets.push([viewport, "resize"], [viewport, "scroll"]);
    for (const [target, name] of targets) target.addEventListener(name, schedule);
    update();
    return () => {
      if (frame !== null) win.cancelAnimationFrame(frame);
      for (const [target, name] of targets) target.removeEventListener(name, schedule);
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
