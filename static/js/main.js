// Confidence Builder AI — main.js

function toggleMenu() {
  const m = document.getElementById('mobileMenu');
  m.classList.toggle('open');
}

// Close mobile menu on outside click
document.addEventListener('click', function(e) {
  const menu = document.getElementById('mobileMenu');
  const burger = document.querySelector('.hamburger');
  if (menu && burger && !menu.contains(e.target) && !burger.contains(e.target)) {
    menu.classList.remove('open');
  }
});

// Animate stats on scroll
function animateNumbers() {
  document.querySelectorAll('.stat-val').forEach(el => {
    const text = el.textContent.trim();
    const num = parseFloat(text.replace(/[^0-9.]/g, ''));
    if (!isNaN(num) && num > 0 && !el.dataset.animated) {
      el.dataset.animated = true;
      let start = 0;
      const suffix = text.replace(/[0-9.]/g, '');
      const duration = 800;
      const step = num / (duration / 16);
      const timer = setInterval(() => {
        start += step;
        if (start >= num) {
          start = num;
          clearInterval(timer);
        }
        el.textContent = Number.isInteger(num)
          ? Math.round(start) + suffix
          : start.toFixed(1) + suffix;
      }, 16);
    }
  });
}

// Run on load
window.addEventListener('load', () => {
  animateNumbers();
  // Progress bars animate in
  document.querySelectorAll('.progress-bar, .ms-bar').forEach(bar => {
    const w = bar.style.width;
    bar.style.width = '0';
    setTimeout(() => { bar.style.width = w; }, 100);
  });
});
