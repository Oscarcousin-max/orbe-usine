(function () {
  var d = document, b = d.body, bar = d.querySelector('.bar'), btn = d.querySelector('.menu-btn');
  d.documentElement.classList.add('js');
  function haut() { bar.classList.toggle('sombre', window.scrollY > 40 || !b.classList.contains('plein')); }
  haut(); window.addEventListener('scroll', haut, { passive: true });
  if (btn) btn.addEventListener('click', function () {
    var o = bar.classList.toggle('ouvert'); btn.setAttribute('aria-expanded', o ? 'true' : 'false'); btn.textContent = o ? 'Fermer' : 'Menu';
  });
  d.querySelectorAll('.bar nav a').forEach(function (a) { a.addEventListener('click', function () { bar.classList.remove('ouvert'); if (btn) { btn.textContent = 'Menu'; btn.setAttribute('aria-expanded', 'false'); } }); });
  var els = d.querySelectorAll('.apparait');
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('vu'); io.unobserve(e.target); } }); }, { rootMargin: '0px 0px -8% 0px' });
    els.forEach(function (e) { io.observe(e); });
  } else { els.forEach(function (e) { e.classList.add('vu'); }); }
  d.querySelectorAll('img').forEach(function (i) { i.addEventListener('error', function () { var f = i.closest('figure, .photo, .a, .b, .fond, .img'); if (f) f.style.display = 'none'; }); });
  var an = d.getElementById('annee'); if (an) an.textContent = new Date().getFullYear();
})();
