(function () {
  // —— Mobile nav ——
  const navInner = document.querySelector(".nav-inner");
  const toggle = document.querySelector(".nav-toggle");
  if (toggle && navInner) {
    toggle.addEventListener("click", () => {
      const open = navInner.classList.toggle("nav-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    document.querySelectorAll(".nav-links a").forEach((link) => {
      link.addEventListener("click", () => {
        navInner.classList.remove("nav-open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  // —— Sticky header shadow on scroll ——
  const header = document.querySelector(".site-header");
  if (header) {
    const onScroll = () => header.classList.toggle("scrolled", window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  // —— FAQ accordion (accessible) ——
  document.querySelectorAll(".faq-question").forEach((btn) => {
    btn.addEventListener("click", () => {
      const item = btn.closest(".faq-item");
      const willOpen = !item.classList.contains("open");
      document.querySelectorAll(".faq-item").forEach((el) => {
        el.classList.remove("open");
        const q = el.querySelector(".faq-question");
        if (q) q.setAttribute("aria-expanded", "false");
      });
      if (willOpen) {
        item.classList.add("open");
        btn.setAttribute("aria-expanded", "true");
      }
    });
  });

  // —— Access forms (mailto + inline confirmation) ——
  document.querySelectorAll(".access-form").forEach((form) => {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const input = form.querySelector('input[type="email"]');
      const email = input ? input.value.trim() : "";
      if (!email) return;
      const subject = encodeURIComponent("EstatePermit early access");
      const body = encodeURIComponent(
        `Please add me to the EstatePermit early access list.\n\nEmail: ${email}`
      );
      window.location.href = `mailto:hello@estatepermit.com?subject=${subject}&body=${body}`;

      const note = form.parentElement
        ? form.parentElement.querySelector(".form-note")
        : null;
      if (note) {
        note.textContent =
          "Thanks — your email client should open. If not, email hello@estatepermit.com.";
        note.classList.add("success");
      }
      form.reset();
    });
  });

  // —— Reveal on scroll ——
  const revealEls = document.querySelectorAll(".reveal");
  if (revealEls.length && "IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("in");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );
    revealEls.forEach((el) => io.observe(el));
  } else {
    revealEls.forEach((el) => el.classList.add("in"));
  }

  // —— Footer year ——
  const year = document.getElementById("year");
  if (year) year.textContent = String(new Date().getFullYear());
})();
