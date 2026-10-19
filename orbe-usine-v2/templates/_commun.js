(function(){
var d=document,r=d.documentElement;r.classList.remove('pas-js');
var top=d.querySelector('.top'),btn=d.querySelector('.menu-btn'),nav=d.querySelector('.top nav');
function onScroll(){if(top)top.classList.toggle('fond',window.scrollY>40);
 var s=window.scrollY;d.querySelectorAll('[data-parallax]').forEach(function(e){e.style.transform='translate3d(0,'+(s*parseFloat(e.dataset.parallax))+'px,0)'});}
window.addEventListener('scroll',onScroll,{passive:true});onScroll();
if(btn){btn.addEventListener('click',function(){var o=btn.getAttribute('aria-expanded')!=='true';btn.setAttribute('aria-expanded',o);nav.classList.toggle('ouvert',o);top.classList.toggle('ouvert-menu',o);d.body.style.overflow=o?'hidden':''});
 nav.addEventListener('click',function(e){if(e.target.tagName==='A'){btn.setAttribute('aria-expanded','false');nav.classList.remove('ouvert');top.classList.remove('ouvert-menu');d.body.style.overflow=''}});}
var els=[].slice.call(d.querySelectorAll('.reveal'));
if('IntersectionObserver' in window){var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('vu');io.unobserve(e.target)}})},{threshold:.12,rootMargin:'0px 0px -6% 0px'});els.forEach(function(e){io.observe(e)})}else{els.forEach(function(e){e.classList.add('vu')})}
d.querySelectorAll('form.demo').forEach(function(f){f.addEventListener('submit',function(e){e.preventDefault();var p=f.querySelector('.retour');if(p)p.textContent='Démonstration : ce formulaire sera relié à votre boîte mail.'})});
var y=d.querySelector('[data-annee]');if(y)y.textContent=new Date().getFullYear();
})();
