
document.addEventListener("DOMContentLoaded", () => {

  // NAV OBSERVER
  const sections = document.querySelectorAll('main section[id]');
  const navLinks = document.querySelectorAll('nav.section-nav a');

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        navLinks.forEach(a => a.classList.remove('active'));
        const active = document.querySelector(`nav.section-nav a[href="#${entry.target.id}"]`);
        if (active) active.classList.add('active');
      }
    });
  }, { threshold: 0.3 });

  sections.forEach(s => observer.observe(s));

  // TOGGLE WARNINGS
  const toggle = document.getElementById("toggle-warnings");

  if (toggle) {
    toggle.addEventListener("change", () => {
      document.body.classList.toggle("hide-warnings", !toggle.checked);
    });
  }
});

function switchMatchTab(targetId, clickedBtn) {
  const section = clickedBtn.closest('section');
  section.querySelectorAll('.match-grid').forEach(function(grid) {
    grid.classList.add('match-grid--hidden');
  });
  section.querySelectorAll('.match-tab').forEach(function(tab) {
    tab.classList.remove('match-tab--active');
  });
  document.getElementById(targetId).classList.remove('match-grid--hidden');
  clickedBtn.classList.add('match-tab--active');
};
 
