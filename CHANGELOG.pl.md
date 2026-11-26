# Historia zmian

[English](CHANGELOG.md) · **Polski**

## 0.1.5 — kandydat rozwojowy (niewydany)

- Naprawa zastępowania nazw encji nazwą urządzenia: tłumaczone encje nie ustawiają już `_attr_name`, również na `None`.
- Test regresji konstruktorów wszystkich tłumaczonych encji w obu językach oraz zachowania identyfikatorów unikatowych.
- Bez zmian poleceń sterownika, konfiguracji zdarzeń i istniejących identyfikatorów webhooków.

## 0.1.4 — kandydat rozwojowy (niewydany)

- Natywne tłumaczenia nazw encji, etykiet zdarzeń wejściowych i błędów w Home Assistancie na język polski i angielski.
- Czytelne moduły Pythona i powtarzalne generowanie jednoplikowego instalatora.
- Zachowanie natywnych zasobów tłumaczeń oraz identyfikatorów unikatowych encji i identyfikatorów zdarzeń.
- Dodatkowe testy regresji tłumaczeń i procesu budowania. Kandydat wymaga jeszcze testów sprzętowych.

## 0.1.3 — beta (2026-11-26)

- Natywne encje zdarzeń HA dla IN1 i IN2.
- Lokalne webhooki z tajnymi identyfikatorami oraz jawna konfiguracja akcji z weryfikacją odczytu.
- Klasyfikacja zdarzeń IN2 na podstawie aktualnego ustawienia przycisku pochwytu.
- Siedem potwierdzonych zdarzeń IN2 na sterowniku W-dU-2.0 z oprogramowaniem 0.1060 i HA Core 2026.11.3.
- Działanie dedykowanego przycisku elektrozaczepu HA potwierdzone na rzeczywistej instalacji przez właściciela.
- Obserwacje API, testy regresji offline i artefakt instalatora w CI.

## 0.1.2

- Pierwsza nakładka WIKĘD: trzy wyjścia LED, oświetlenie czasowe, ustawienie pochwytu, S1/S2, opcjonalny elektrozaczep oraz natywne encje aktualizacji i bramy.
