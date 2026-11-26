# Bezpieczeństwo

[English](SECURITY.md) · **Polski**

Projekt steruje fizycznymi urządzeniami kontroli dostępu. Podejrzenia podatności zgłaszaj prywatnie opiekunowi repozytorium. Nie publikuj identyfikatorów webhooków, tokenów dostępu, prywatnych adresów URL, przechwyconego ruchu sieciowego ani szczegółów konfiguracji domu w publicznych zgłoszeniach. Jeżeli w GitHubie dostępne jest prywatne zgłaszanie podatności, skorzystaj z tej funkcji.

## Zasady bezpieczeństwa

- Natywne warunkowe zwalnianie elektrozaczepu pozostaje dostępne; odebranie zdarzenia nie otwiera drzwi.
- Identyfikatory webhooków są tajne, trwałe i przeznaczone do użycia lokalnego. Utrzymuj HA i sterownik w zaufanej sieci. Lokalny HTTP nie jest szyfrowany.
- Nigdy nie wystawiaj API sterownika bezpośrednio do internetu.
- Zapis konfiguracji wymaga jawnego działania użytkownika i odbywa się w odrębnych miejscach na akcje. Przed konfiguracją wykonaj kopię zapasową ustawień.
- S1/S2 oznaczają sygnały zamka, nie potwierdzenie domknięcia skrzydła.
- Wersję beta przetestowano w zakresie opisanym w README. Inne wersje i sposoby podłączenia mogą zachowywać się inaczej.
