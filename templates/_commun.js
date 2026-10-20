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
/* Kit premium ORBE : titre animé, lumière, barre de progression, tuiles empilées, icônes 3D, bouton aimanté */
(function(){
var d=document,w=window,calme=w.matchMedia&&w.matchMedia('(prefers-reduced-motion: reduce)').matches;
d.querySelectorAll('.hero h1').forEach(function(h){var n=0;[].slice.call(h.childNodes).forEach(function(t){if(t.nodeType!==3||!t.textContent.trim())return;var f=d.createDocumentFragment();t.textContent.split(/(\s+)/).forEach(function(m){if(!m)return;if(/^\s+$/.test(m)){f.appendChild(d.createTextNode(' '));return}var o=d.createElement('k-m');var b=d.createElement('k-w');b.textContent=m;b.style.setProperty('--m',n++);o.appendChild(b);f.appendChild(o)});h.replaceChild(f,t)})});
var hero=d.querySelector('.hero');
if(hero&&!calme){hero.addEventListener('pointermove',function(e){var r=hero.getBoundingClientRect();hero.style.setProperty('--mx',(e.clientX-r.left)+'px');hero.style.setProperty('--my',(e.clientY-r.top)+'px')})}
d.querySelectorAll('.verre').forEach(function(v){v.addEventListener('pointermove',function(e){var r=v.getBoundingClientRect();v.style.setProperty('--lx',((e.clientX-r.left)/r.width*100)+'%');v.style.setProperty('--ly',((e.clientY-r.top)/r.height*100)+'%')})});
var bar=d.querySelector('.progres'),tu=[].slice.call(d.querySelectorAll('.tuile')),idx=[].slice.call(d.querySelectorAll('.tuiles-index li'));
var att=false;function maj(){att=false;var h=d.documentElement.scrollHeight-w.innerHeight;if(bar)bar.style.setProperty('--p',h>0?Math.min(1,w.scrollY/h):0);
 var act=0;tu.forEach(function(t,i){var r=t.getBoundingClientRect();if(r.top<w.innerHeight*.55)act=i;if(calme)return;var s=tu[i+1];if(!s){t.style.setProperty('--s',1);t.style.setProperty('--b',1);return}
  var q=s.getBoundingClientRect(),k=Math.max(0,Math.min(1,1-(q.top-r.top)/(r.height||1)));t.style.setProperty('--s',(1-k*.06).toFixed(4));t.style.setProperty('--b',(1-k*.12).toFixed(4))});
 idx.forEach(function(l,i){l.classList.toggle('actif',i===act)});}
w.addEventListener('scroll',function(){if(!att){att=true;requestAnimationFrame(maj)}},{passive:true});w.addEventListener('resize',maj);maj();
if(!calme&&w.matchMedia('(hover: hover)').matches){
 d.querySelectorAll('.ico3d').forEach(function(c){var t=c.closest('.tuile')||c;t.addEventListener('pointermove',function(e){var r=c.getBoundingClientRect(),x=(e.clientX-r.left)/r.width-.5,y=(e.clientY-r.top)/r.height-.5;c.style.setProperty('--ry',(x*28)+'deg');c.style.setProperty('--rx',(-y*28)+'deg')});t.addEventListener('pointerleave',function(){c.style.setProperty('--ry','0deg');c.style.setProperty('--rx','0deg')})});
 d.querySelectorAll('.aimant').forEach(function(b){b.addEventListener('pointermove',function(e){var r=b.getBoundingClientRect();b.style.transform='translate('+((e.clientX-r.left-r.width/2)*.18)+'px,'+((e.clientY-r.top-r.height/2)*.28)+'px)'});b.addEventListener('pointerleave',function(){b.style.transform=''})});}
})();
(function(){var n=document.querySelector('.pied-nom');if(!n)return;function fit(){n.style.fontSize='';var t=0;while(n.scrollWidth>n.clientWidth+2&&t++<40){n.style.fontSize=(parseFloat(getComputedStyle(n).fontSize)*.94)+'px'}}
fit();window.addEventListener('resize',fit);if(document.fonts&&document.fonts.ready)document.fonts.ready.then(fit);})();
