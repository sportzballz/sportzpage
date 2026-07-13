/* static/js/daily-sports-page.js */
/* SportzBallz Daily Sports Page — Progressive Enhancement JS
 * Vanilla ES2022. No framework. Degrades gracefully without JS.
 */

(function () {
  "use strict";

  const prefersReducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)",
  ).matches;

  // Apply reduced-motion class so CSS can opt out of transitions
  if (prefersReducedMotion) {
    document.documentElement.classList.add("reduce-motion");
  }

  document.addEventListener("DOMContentLoaded", () => {
    initLeadersTabs();
    initSectionCollapse();
    initCopyLinkButtons();
    initPrintButton();
  });

  /* =========================================================
     1. LEAGUE LEADER TABS
     ========================================================= */

  function initLeadersTabs() {
    const tabbedGroups = document.querySelectorAll(".leaders-tablist");

    tabbedGroups.forEach((tablist) => {
      const groupId = tablist.dataset.tablistId;
      const tabs = Array.from(tablist.querySelectorAll(".leaders-tab"));
      const panelsContainer = tablist
        .closest(".leaders-tab-group")
        ?.querySelector(".leaders-panels");

      if (!tabs.length || !panelsContainer) return;

      const panels = Array.from(
        panelsContainer.querySelectorAll(".leaders-panel"),
      );

      // Restore saved tab from sessionStorage
      const storageKey = `leaders-active-tab-${groupId}`;
      const savedCategory = sessionStorage.getItem(storageKey);

      function activateTab(targetTab) {
        tabs.forEach((tab) => {
          const isTarget = tab === targetTab;
          tab.setAttribute("aria-selected", isTarget ? "true" : "false");
          tab.setAttribute("tabindex", isTarget ? "0" : "-1");
          tab.classList.toggle("leaders-tab-active", isTarget);
        });

        panels.forEach((panel) => {
          const controlled = targetTab.getAttribute("aria-controls");
          const isVisible = panel.id === controlled;
          panel.style.display = isVisible ? "block" : "none";
        });

        sessionStorage.setItem(storageKey, targetTab.dataset.category ?? "");
      }

      // Initialize: hide all panels first, then show the correct one
      panels.forEach((p) => {
        p.style.display = "none";
      });

      // Find the tab to activate initially
      let initialTab =
        tabs.find((t) => t.dataset.category === savedCategory) ?? tabs[0];

      if (initialTab) activateTab(initialTab);

      // Click handler
      tabs.forEach((tab) => {
        tab.addEventListener("click", () => activateTab(tab));
      });

      // Arrow key navigation
      tablist.addEventListener("keydown", (e) => {
        const currentIndex = tabs.indexOf(document.activeElement);
        if (currentIndex === -1) return;

        let nextIndex = currentIndex;

        if (e.key === "ArrowRight" || e.key === "ArrowDown") {
          e.preventDefault();
          nextIndex = (currentIndex + 1) % tabs.length;
        } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
          e.preventDefault();
          nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
        } else if (e.key === "Home") {
          e.preventDefault();
          nextIndex = 0;
        } else if (e.key === "End") {
          e.preventDefault();
          nextIndex = tabs.length - 1;
        } else {
          return;
        }

        tabs[nextIndex].focus();
        activateTab(tabs[nextIndex]);
      });
    });
  }

  /* =========================================================
     2. COPY LINK BUTTONS
     ========================================================= */

  function initCopyLinkButtons() {
    if (!navigator.clipboard) return;

    // Sections: add copy button next to section headings
    const sections = document.querySelectorAll("section[id]");
    sections.forEach((section) => {
      const heading = section.querySelector("h2.section-heading");
      if (!heading) return;
      heading.appendChild(makeCopyBtn(`#${section.id}`, "section"));
    });

    // Game recaps: add copy button to each recap
    const recaps = document.querySelectorAll(".game-recap[id]");
    recaps.forEach((recap) => {
      const heading = recap.querySelector("h3");
      if (!heading) return;
      heading.appendChild(makeCopyBtn(`#${recap.id}`, "recap"));
    });
  }

  function makeCopyBtn(anchor, context) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "copy-link-btn";
    btn.textContent = "Copy link";
    btn.setAttribute("aria-label", `Copy link to this ${context}`);
    btn.setAttribute("data-print", "hide");

    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const url = `${location.origin}${location.pathname}${anchor}`;
      try {
        await navigator.clipboard.writeText(url);
        const original = btn.textContent;
        btn.textContent = "Copied!";
        setTimeout(() => {
          btn.textContent = original;
        }, 1500);
      } catch {
        // Clipboard write failed silently — degraded gracefully
      }
    });

    return btn;
  }

  /* =========================================================
     3. SECTION COLLAPSE / EXPAND
     ========================================================= */

  function initSectionCollapse() {
    const sections = document.querySelectorAll("section[id]");

    sections.forEach((section) => {
      const heading = section.querySelector("h2.section-heading");
      if (!heading) return;

      // Wrap everything after heading in a collapsible div
      const children = Array.from(section.children).filter(
        (el) => el !== heading,
      );
      if (!children.length) return;

      const collapseId = `collapse-${section.id}`;
      const body = document.createElement("div");
      body.id = collapseId;
      body.className = "section-body";

      children.forEach((child) => body.appendChild(child));
      section.appendChild(body);

      // Make heading a toggle button (accessible)
      heading.setAttribute("role", "button");
      heading.setAttribute("tabindex", "0");
      heading.setAttribute("aria-expanded", "true");
      heading.setAttribute("aria-controls", collapseId);
      heading.style.cursor = "pointer";
      heading.style.userSelect = "none";

      function toggle() {
        const expanded = heading.getAttribute("aria-expanded") === "true";
        heading.setAttribute("aria-expanded", expanded ? "false" : "true");
        body.style.display = expanded ? "none" : "";
      }

      heading.addEventListener("click", toggle);
      heading.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          toggle();
        }
      });
    });
  }

  /* =========================================================
     4. PRINT BUTTON
     ========================================================= */

  function initPrintButton() {
    // Print buttons in the page use onclick="window.print()" inline
    // This is a fallback for any print buttons without inline handlers
    document.querySelectorAll(".print-btn:not([onclick])").forEach((btn) => {
      btn.addEventListener("click", () => window.print());
    });
  }
})();
