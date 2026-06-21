(function () {
  const navInner = document.querySelector(".nav-inner");
  const toggle = document.querySelector(".nav-toggle");
  if (toggle && navInner) {
    toggle.addEventListener("click", () => {
      navInner.classList.toggle("nav-open");
      toggle.setAttribute(
        "aria-expanded",
        navInner.classList.contains("nav-open") ? "true" : "false"
      );
    });
    document.querySelectorAll(".nav-links a").forEach((link) => {
      link.addEventListener("click", () => navInner.classList.remove("nav-open"));
    });
  }

  document.querySelectorAll(".faq-question").forEach((btn) => {
    btn.addEventListener("click", () => {
      const item = btn.closest(".faq-item");
      const open = item.classList.contains("open");
      document.querySelectorAll(".faq-item").forEach((el) => el.classList.remove("open"));
      if (!open) item.classList.add("open");
    });
  });

  const waitlist = document.getElementById("waitlist-form");
  if (waitlist) {
    waitlist.addEventListener("submit", (e) => {
      e.preventDefault();
      const email = waitlist.querySelector('input[type="email"]').value.trim();
      if (!email) return;
      const subject = encodeURIComponent("EstatePermit early access");
      const body = encodeURIComponent(`Please add me to the EstatePermit early access list.\n\nEmail: ${email}`);
      window.location.href = `mailto:hello@estatepermit.com?subject=${subject}&body=${body}`;
    });
  }

  const year = document.getElementById("year");
  if (year) year.textContent = String(new Date().getFullYear());

  const themeParam = new URLSearchParams(window.location.search).get("theme");
  const allowed = ["slate", "forest", "ink"];
  if (themeParam && allowed.includes(themeParam)) {
    document.documentElement.setAttribute("data-theme", themeParam);
  }
})();
