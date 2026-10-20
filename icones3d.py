"""Icônes « 3D » des tuiles : formes pleines, éclairées par un filtre SVG (relief + reflet).

Classes : p = matière principale, s = matière secondaire, h = reflet blanc.
Les couleurs viennent du thème du site (variables --ic1 à --ic4).
"""

_I = {
    "calendrier": '<rect class="p" x="8" y="12" width="48" height="44" rx="10"/><path class="s" d="M8 22a10 10 0 0 1 10-10h28a10 10 0 0 1 10 10v4H8z"/>'
                  '<rect class="s" x="18" y="6" width="6" height="14" rx="3"/><rect class="s" x="40" y="6" width="6" height="14" rx="3"/>'
                  '<g class="h"><rect x="17" y="34" width="7" height="7" rx="2"/><rect x="28.5" y="34" width="7" height="7" rx="2"/><rect x="40" y="34" width="7" height="7" rx="2"/><rect x="17" y="45" width="7" height="5" rx="2"/></g>',
    "verre": '<path class="p" d="M16 6h32c1 12-2 26-16 28C18 32 15 18 16 6Z"/><rect class="s" x="29.5" y="32" width="5" height="18" rx="2.5"/>'
             '<ellipse class="s" cx="32" cy="54" rx="14" ry="4.5"/><path class="h" d="M21 11c0 7 1 13 5 17-6-2-8-9-7-17z" opacity=".5"/>',
    "bouteille": '<path class="p" d="M27 4h10v12c0 3 9 6 9 16v22a6 6 0 0 1-6 6H24a6 6 0 0 1-6-6V32c0-10 9-13 9-16Z"/>'
                 '<rect class="s" x="26" y="2" width="12" height="7" rx="2.5"/><rect class="s" x="18" y="36" width="28" height="14"/>'
                 '<path class="h" d="M23 30c0-4 2-7 5-9-1 4-1 20-1 26h-4z" opacity=".45"/>',
    "bulle": '<path class="p" d="M10 14a10 10 0 0 1 10-10h24a10 10 0 0 1 10 10v18a10 10 0 0 1-10 10H28l-12 11v-11h0a6 6 0 0 1-6-6Z"/>'
             '<g class="h" opacity=".9"><circle cx="22" cy="23" r="3.6"/><circle cx="32" cy="23" r="3.6"/><circle cx="42" cy="23" r="3.6"/></g>',
    "fleur": '<g class="s"><ellipse cx="32" cy="15" rx="9" ry="12"/><ellipse cx="32" cy="15" rx="9" ry="12" transform="rotate(72 32 30)"/>'
             '<ellipse cx="32" cy="15" rx="9" ry="12" transform="rotate(144 32 30)"/><ellipse cx="32" cy="15" rx="9" ry="12" transform="rotate(216 32 30)"/>'
             '<ellipse cx="32" cy="15" rx="9" ry="12" transform="rotate(288 32 30)"/></g><circle class="p" cx="32" cy="30" r="9"/>'
             '<path class="p" d="M30.5 40h3v20h-3z"/><circle class="h" cx="29" cy="27" r="2.6" opacity=".6"/>',
    "cadeau": '<rect class="p" x="9" y="26" width="46" height="32" rx="6"/><rect class="s" x="6" y="18" width="52" height="12" rx="5"/>'
              '<rect class="h" x="28.5" y="18" width="7" height="40" opacity=".75"/><path class="s" d="M32 18c-4-10-16-12-16-4 0 4 8 4 16 4Zm0 0c4-10 16-12 16-4 0 4-8 4-16 4Z"/>',
    "gemme": '<path class="s" d="M20 8h24l12 14H8Z"/><path class="p" d="M8 22h48L32 58Z"/><path class="h" d="M20 8l6 14h12l6-14Z" opacity=".35"/>'
             '<path class="h" d="M26 22h12L32 52Z" opacity=".25"/>',
    "loupe": '<circle class="s" cx="27" cy="27" r="19"/><circle cx="27" cy="27" r="12" style="fill:var(--bg)"/><path class="h" d="M18 22a10 10 0 0 1 9-7" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round" opacity=".8"/>'
             '<rect class="p" x="38" y="40" width="10" height="22" rx="5" transform="rotate(-45 43 51)"/>',
    "etoile": '<path class="p" d="M32 4c2 14 6 22 26 28-20 6-24 14-26 28-2-14-6-22-26-28 20-6 24-14 26-28Z"/>'
              '<path class="s" d="M50 4c1 6 2 8 8 9-6 1-7 3-8 9-1-6-2-8-8-9 6-1 7-3 8-9Z"/>',
    "enveloppe": '<rect class="p" x="6" y="14" width="52" height="38" rx="8"/><path class="s" d="M8 18l24 18 24-18v-1a8 8 0 0 0-3-3H11a8 8 0 0 0-3 3Z"/>'
                 '<path class="h" d="M12 18l20 15 20-15" fill="none" stroke="#fff" stroke-width="2" opacity=".6"/>',
    "repere": '<path class="p" d="M32 4c12 0 21 9 21 21 0 15-21 35-21 35S11 40 11 25C11 13 20 4 32 4Z"/><circle cx="32" cy="25" r="8" style="fill:var(--bg)"/>'
              '<ellipse class="s" cx="32" cy="60" rx="12" ry="3" opacity=".5"/>',
    "coeur": '<path class="p" d="M32 56S6 41 6 22C6 13 13 7 21 7c5 0 9 3 11 7 2-4 6-7 11-7 8 0 15 6 15 15 0 19-26 34-26 34Z"/>'
             '<path class="h" d="M14 20c0-5 4-8 8-8-3 2-5 5-5 9z" opacity=".6"/>',
    "crayon": '<path class="p" d="M44 6l14 14-30 30-14-14Z"/><path class="s" d="M14 36l14 14-20 6Z"/><path class="s" d="M44 6l5-5 14 14-5 5Z"/>'
              '<path class="h" d="M41 12l4 4-24 24-4-4Z" opacity=".35"/>',
    "cube": '<path class="s" d="M32 4l26 14-26 14L6 18Z"/><path class="p" d="M6 18l26 14v28L6 46Z"/><path class="p" d="M58 18L32 32v28l26-14Z" style="filter:url(#relief) brightness(.78)"/>',
}

PAR_FAMILLE = {
    "domaine": ("calendrier", "verre", "bouteille"),
    "fleur": ("bulle", "fleur", "cadeau"),
    "bijou": ("bulle", "loupe", "gemme"),
    "table": ("enveloppe", "repere", "coeur"),
    "atelier": ("bulle", "crayon", "cube"),
}


def icones(famille, noms=None):
    noms = noms or PAR_FAMILLE.get(famille, ("bulle", "etoile", "coeur"))
    return ['<svg viewBox="0 0 64 64" aria-hidden="true" focusable="false">%s</svg>' % _I[n] for n in noms]
