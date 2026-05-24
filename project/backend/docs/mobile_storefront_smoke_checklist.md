# Mobil storefront smoke checklist (manuális QA)

Rövid, konkrét lista deploy / Barion sandbox előtt. DevTools → device toolbar.

## Viewportok

- [ ] **360×800** (kis Android)
- [ ] **390×844** (iPhone 14 körül)
- [ ] **430×932** (nagyobb telefon)
- [ ] **768px** (tablet határ — desktop nav ne jöjjön vissza túl korán)

## Auth

- [ ] Regisztráció → verify e-mail (ha SMTP)
- [ ] Login / logout
- [ ] Nem verified user: komment űrlap rejtve, hint látszik

## Webshop / kosár / checkout

- [ ] Terméklista betölt
- [ ] Kosár FAB nem takarja a CTA-t (kosár nézetben rejtve)
- [ ] Checkout: kupon, submit **egy** kattintás (dupla POST ne legyen)
- [ ] Barion redirect (sandbox)
- [ ] Return: üzenet **nem** zöld, ha nincs backend `paid` verify
- [ ] Return `payment=error` → érthető hiba + Rendeléseim útmutató
- [ ] Megszakított fizetés: kosár üres lehet, de Rendeléseim + **Fizetés újrapróbálása** látszik

## Hírek / komment

- [ ] Featured hír + komment zóna
- [ ] Üres komment tiltva
- [ ] Valid komment megjelenik a listában (azonnali publikálás szöveg)
- [ ] API hiba piros üzenet

## Galéria

- [ ] Galéria nézet: loading → képek vagy üres állapot
- [ ] Hibás kép nem töri szét a layoutot

## Mesekönyv

- [ ] Lista + reader
- [ ] Előző / következő / vissza gombok ≥44px
- [ ] Audio vezérlők használhatók

## Fiók

- [ ] Rendeléseim olvasható, nincs vízszintes szétesés
- [ ] Profil mentés

## Egyéb

- [ ] Hamburger: nyit/zár, backdrop, ESC
- [ ] Legal / footer: nincs overflow
- [ ] iOS Safari: nincs jumpy `background-attachment` (scroll mód)

**Jegyzet:** Barion éles kártya + IPN csak sandbox/éles környezetben teljes E2E.
