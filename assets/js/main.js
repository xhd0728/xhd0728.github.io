/* ==========================================================================
   Main JS — Vanilla ES6+ replacement for jQuery + plugins
   ========================================================================== */
(function () {
  "use strict";

  /* ------------------------------------------------------------------
     Greedy Navigation (Priority+ pattern)
     ------------------------------------------------------------------ */
  function initGreedyNav() {
    var nav = document.querySelector(".greedy-nav");
    if (!nav) return;
    var btn = nav.querySelector(".greedy-nav__toggle");
    var visibleList = nav.querySelector(".visible-links");
    var hiddenList = nav.querySelector(".hidden-links");
    var langMenu = nav.querySelector(".masthead__lang-menu");
    if (!btn || !visibleList || !hiddenList) return;
    var breaks = [];
    var resizePending = false;

    function closeNav(returnFocus) {
      hiddenList.classList.add("hidden");
      btn.classList.remove("close");
      btn.setAttribute("aria-expanded", "false");
      if (returnFocus) btn.focus();
    }

    function openNav() {
      hiddenList.classList.remove("hidden");
      btn.classList.add("close");
      btn.setAttribute("aria-expanded", "true");
    }

    function width(el) {
      return Math.ceil(el.getBoundingClientRect().width);
    }

    function updateNav() {
      var langToggle = langMenu
        ? langMenu.querySelector(".lang-menu__trigger")
        : null;
      var langMenuWidth = langMenu
        ? Math.max(width(langMenu), langToggle ? width(langToggle) : 0) + 18
        : 0;
      var availableSpace = btn.classList.contains("hidden")
        ? width(nav) - langMenuWidth
        : width(nav) - width(btn) - langMenuWidth - 30;
      if (width(visibleList) > availableSpace) {
        var lastVisibleItem = visibleList.lastElementChild;
        if (!lastVisibleItem) return;
        breaks.push(width(visibleList));
        hiddenList.prepend(lastVisibleItem);
        btn.classList.remove("hidden");
      } else {
        while (
          breaks.length > 0 &&
          availableSpace > breaks[breaks.length - 1]
        ) {
          var firstHiddenItem = hiddenList.firstElementChild;
          if (!firstHiddenItem) break;
          visibleList.append(firstHiddenItem);
          breaks.pop();
        }
        if (breaks.length < 1) {
          btn.classList.add("hidden");
          closeNav(false);
        }
      }
      if (
        width(visibleList) > availableSpace &&
        visibleList.children.length > 0
      )
        updateNav();
    }

    function scheduleResize() {
      if (resizePending) return;
      resizePending = true;
      window.requestAnimationFrame(function () {
        updateNav();
        if (
          hiddenList.contains(document.activeElement) &&
          hiddenList.classList.contains("hidden")
        )
          btn.focus();
        var masthead = document.querySelector(".masthead");
        if (masthead)
          document.documentElement.style.setProperty(
            "--masthead-height",
            Math.ceil(masthead.getBoundingClientRect().height) + "px",
          );
        resizePending = false;
      });
    }

    // Native anchor navigation preserves history, modifier clicks and the language path.
    nav.querySelectorAll('a[href*="#"]').forEach(function (link) {
      var url = new URL(link.href);
      if (
        url.origin !== window.location.origin ||
        url.pathname !== window.location.pathname
      )
        return;
      link.addEventListener("click", function () {
        closeNav(false);
      });
    });
    btn.classList.add("hidden");
    btn.addEventListener("click", function () {
      if (hiddenList.classList.contains("hidden")) openNav();
      else closeNav(false);
    });
    btn.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      e.preventDefault();
      openNav();
      var items = hiddenList.querySelectorAll("a");
      if (items.length)
        items[e.key === "ArrowDown" ? 0 : items.length - 1].focus();
    });
    hiddenList.addEventListener("keydown", function (e) {
      var items = Array.prototype.slice.call(hiddenList.querySelectorAll("a"));
      var index = items.indexOf(document.activeElement);
      if (!items.length) return;
      if (
        e.key === "ArrowDown" ||
        e.key === "ArrowUp" ||
        e.key === "Home" ||
        e.key === "End"
      ) {
        e.preventDefault();
        if (e.key === "Home") index = 0;
        else if (e.key === "End") index = items.length - 1;
        else
          index =
            (index + (e.key === "ArrowDown" ? 1 : -1) + items.length) %
            items.length;
        items[index].focus();
      }
    });
    hiddenList.addEventListener("click", function (e) {
      if (e.target.closest("a")) closeNav(false);
    });
    nav.addEventListener("focusout", function (e) {
      if (!nav.contains(e.relatedTarget)) closeNav(false);
    });
    document.addEventListener("click", function (e) {
      if (!nav.contains(e.target) || (langMenu && langMenu.contains(e.target)))
        closeNav(false);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !hiddenList.classList.contains("hidden")) {
        e.preventDefault();
        closeNav(true);
      }
    });
    window.addEventListener("resize", scheduleResize);
    if ("ResizeObserver" in window) {
      new ResizeObserver(scheduleResize).observe(nav);
    }
    if (document.fonts) document.fonts.ready.then(scheduleResize);
    scheduleResize();
  }

  function initSectionTracking() {
    var nav = document.getElementById("site-nav");
    var sections = document.querySelectorAll(".page__content > .anchor[id]");
    if (!nav || !sections.length) return;
    var links = Array.prototype.slice.call(
      nav.querySelectorAll(
        '.masthead__menu-item:not(.masthead__menu-home-item) a[href*="#"]',
      ),
    );
    var scheduled = false;
    var activeId = "";
    var requestedId = window.location.hash.slice(1);
    function update() {
      var masthead = document.querySelector(".masthead");
      var threshold =
        (masthead ? masthead.getBoundingClientRect().height : 68) + 48;
      var current = sections[0].id;
      sections.forEach(function (section) {
        if (section.getBoundingClientRect().top <= threshold)
          current = section.id;
      });
      var requested = document.getElementById(requestedId);
      if (
        requested &&
        requested.classList.contains("anchor") &&
        requested.getBoundingClientRect().top < window.innerHeight &&
        requested.getBoundingClientRect().top >= threshold - 80
      )
        current = requestedId;
      else if (
        window.scrollY > 0 &&
        window.scrollY + window.innerHeight >=
          document.documentElement.scrollHeight - 4
      )
        current = sections[sections.length - 1].id;
      if (current !== activeId) {
        links.forEach(function (link) {
          if (new URL(link.href).hash === "#" + current)
            link.setAttribute("aria-current", "location");
          else link.removeAttribute("aria-current");
        });
        activeId = current;
      }
      scheduled = false;
    }
    function schedule() {
      if (!scheduled) {
        scheduled = true;
        window.requestAnimationFrame(update);
      }
    }
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    window.addEventListener("hashchange", function () {
      requestedId = window.location.hash.slice(1);
      schedule();
    });
    function resumeTracking() {
      requestedId = "";
      schedule();
    }
    window.addEventListener("wheel", resumeTracking, { passive: true });
    window.addEventListener("touchmove", resumeTracking, { passive: true });
    window.addEventListener("keydown", function (e) {
      if (
        !e.target.closest("nav, dialog, input, textarea") &&
        [
          "ArrowDown",
          "ArrowUp",
          "PageDown",
          "PageUp",
          "Home",
          "End",
          " ",
        ].indexOf(e.key) !== -1
      )
        resumeTracking();
    });
    window.addEventListener("pageshow", schedule);
    schedule();
  }

  /* ------------------------------------------------------------------
     Language dropdown
     ------------------------------------------------------------------ */
  function initLanguageMenu() {
    var menu = document.querySelector("[data-lang-menu]");
    if (!menu) return;

    var trigger = menu.querySelector(".lang-menu__trigger");
    var panel = menu.querySelector(".lang-menu__panel");
    if (!trigger || !panel) return;

    var closeTimer = null;

    // Keep the reader in the same section when changing language.
    menu.querySelectorAll("a.lang-menu__option").forEach(function (link) {
      var base = link.getAttribute("href").split("#")[0];
      function syncHash() {
        link.setAttribute("href", base + window.location.hash);
      }
      syncHash();
      trigger.addEventListener("click", syncHash);
      trigger.addEventListener("keydown", syncHash);
      window.addEventListener("hashchange", syncHash);
    });

    function getItems() {
      return Array.prototype.slice.call(
        panel.querySelectorAll(".lang-menu__option[href]"),
      );
    }

    function isOpen() {
      return menu.classList.contains("is-open");
    }

    function focusItem(position) {
      var items = getItems();
      if (!items.length) return;

      if (position === "last") {
        items[items.length - 1].focus();
        return;
      }

      items[0].focus();
    }

    function openMenu(focusTarget) {
      if (closeTimer) {
        window.clearTimeout(closeTimer);
        closeTimer = null;
      }

      panel.hidden = false;
      trigger.setAttribute("aria-expanded", "true");

      window.requestAnimationFrame(function () {
        menu.classList.add("is-open");
        if (focusTarget) {
          focusItem(focusTarget);
        }
      });
    }

    function closeMenu(returnFocus) {
      if (!isOpen() && panel.hidden) return;

      menu.classList.remove("is-open");
      trigger.setAttribute("aria-expanded", "false");

      if (closeTimer) {
        window.clearTimeout(closeTimer);
      }

      closeTimer = window.setTimeout(function () {
        if (!menu.classList.contains("is-open")) {
          panel.hidden = true;
        }
        closeTimer = null;
      }, 220);

      if (returnFocus) {
        trigger.focus();
      }
    }

    function moveFocus(step) {
      var items = getItems();
      if (!items.length) return;

      if (!isOpen()) {
        openMenu(step > 0 ? "first" : "last");
        return;
      }

      var currentIndex = items.indexOf(document.activeElement);
      var nextIndex =
        currentIndex === -1
          ? step > 0
            ? 0
            : items.length - 1
          : (currentIndex + step + items.length) % items.length;

      items[nextIndex].focus();
    }

    trigger.addEventListener("click", function () {
      if (isOpen()) {
        closeMenu(false);
      } else {
        openMenu();
      }
    });

    trigger.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        moveFocus(1);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        moveFocus(-1);
      } else if (e.key === "Escape") {
        closeMenu(false);
      }
    });

    panel.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        moveFocus(1);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        moveFocus(-1);
      } else if (e.key === "Home") {
        e.preventDefault();
        focusItem("first");
      } else if (e.key === "End") {
        e.preventDefault();
        focusItem("last");
      } else if (e.key === "Escape") {
        e.preventDefault();
        closeMenu(true);
      }
    });

    panel.addEventListener("click", function (e) {
      if (e.target && e.target.closest("a")) {
        closeMenu(false);
      }
    });

    document.addEventListener("click", function (e) {
      if (!menu.contains(e.target)) {
        closeMenu(false);
      }
    });

    menu.addEventListener("focusout", function (e) {
      if (!menu.contains(e.relatedTarget)) closeMenu(false);
    });

    window.addEventListener("resize", function () {
      closeMenu(false);
    });
  }

  function initLightbox() {
    var links = document.querySelectorAll(".paper-image-link");
    if (!links.length) return;
    var dialog = document.createElement("dialog");
    // Keep native full-size links in browsers without dialog support.
    if (typeof dialog.showModal !== "function") return;
    var zh = document.documentElement.lang === "zh-CN";
    dialog.className = "lightbox-dialog";
    dialog.setAttribute("aria-label", zh ? "图片预览" : "Image preview");
    dialog.innerHTML =
      '<button type="button" class="lightbox-close" aria-label="' +
      (zh ? "关闭图片预览" : "Close image preview") +
      '">&times;</button>' +
      '<img class="lightbox-img" alt="">' +
      '<p class="lightbox-status" role="status"></p>' +
      '<div class="lightbox-caption"><span></span><a target="_blank" rel="noopener noreferrer">' +
      (zh ? "查看原图" : "Open full size") +
      "</a></div>";
    document.body.appendChild(dialog);
    var img = dialog.querySelector(".lightbox-img");
    var status = dialog.querySelector(".lightbox-status");
    var closeBtn = dialog.querySelector(".lightbox-close");
    var caption = dialog.querySelector(".lightbox-caption span");
    var original = dialog.querySelector(".lightbox-caption a");
    original.href = links[0].href;
    var previousFocus = null;
    var closingTimer = null;
    var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

    img.addEventListener("load", function () {
      status.hidden = true;
    });
    img.addEventListener("error", function () {
      status.hidden = false;
      status.textContent = zh
        ? "图片暂时无法加载，可尝试打开原图。"
        : "Image unavailable. Try opening the full-size image.";
    });
    function open(link) {
      if (closingTimer) window.clearTimeout(closingTimer);
      dialog.classList.remove("is-closing");
      previousFocus = link;
      var preview = link.querySelector("img");
      var description = preview ? preview.alt : "";
      caption.textContent = description;
      original.href = link.href;
      status.hidden = false;
      status.textContent = zh ? "正在加载图片…" : "Loading image…";
      img.alt = description;
      img.src = link.href;
      dialog.showModal();
      document.body.classList.add("lightbox-open");
    }
    function close() {
      if (!dialog.open || dialog.classList.contains("is-closing")) return;
      if (reducedMotion.matches) {
        dialog.close();
        return;
      }
      dialog.classList.add("is-closing");
      closingTimer = window.setTimeout(function () {
        dialog.close();
      }, 180);
    }
    links.forEach(function (link) {
      link.setAttribute("role", "button");
      link.setAttribute("aria-haspopup", "dialog");
      link.addEventListener("click", function (e) {
        if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)
          return;
        e.preventDefault();
        open(link);
      });
      link.addEventListener("keydown", function (e) {
        if (e.key === " ") {
          e.preventDefault();
          open(link);
        }
      });
    });
    closeBtn.addEventListener("click", close);
    dialog.addEventListener("click", function (e) {
      if (e.target === dialog) close();
    });
    dialog.addEventListener("cancel", function (e) {
      e.preventDefault();
      close();
    });
    dialog.addEventListener("close", function () {
      dialog.classList.remove("is-closing");
      document.body.classList.remove("lightbox-open");
      img.removeAttribute("src");
      img.alt = "";
      closingTimer = null;
      if (previousFocus) previousFocus.focus({ preventScroll: true });
    });
  }

  function initBackToTop() {
    var link = document.getElementById("back-to-top");
    if (!link) return;
    var scheduled = false;
    function update() {
      link.classList.toggle("visible", window.scrollY > 300);
      scheduled = false;
    }
    window.addEventListener(
      "scroll",
      function () {
        if (!scheduled) {
          scheduled = true;
          window.requestAnimationFrame(update);
        }
      },
      { passive: true },
    );
    window.addEventListener("pageshow", update);
    update();
  }

  function initExternalLinks() {
    document
      .querySelectorAll(".page__content a[href], .sidebar a[href]")
      .forEach(function (link) {
        if (
          /^https?:$/.test(link.protocol) &&
          link.origin !== window.location.origin
        ) {
          link.target = "_blank";
          link.rel = "noopener noreferrer";
        }
      });
  }

  function initPage() {
    initGreedyNav();
    initLanguageMenu();
    initSectionTracking();
    initLightbox();
    initBackToTop();
    initExternalLinks();
  }

  /* ------------------------------------------------------------------
     Init when DOM is ready
     ------------------------------------------------------------------ */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPage, { once: true });
  } else {
    initPage();
  }
})();
