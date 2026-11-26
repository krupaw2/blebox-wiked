# Obserwacje lokalnego API

[English](API.md) · **Polski**

Urządzenie: `doorUnitBox_v2`, typ `gateBox`, sprzęt `W-dU-2.0`, oprogramowanie `0.1060`, poziom API `20230102`, poziom API rozszerzeń `20220713`.

Odpowiedź `/info` udostępnia rozszerzenia typu switch o identyfikatorach 0–2 (LED 1–3), settingsSwitch o identyfikatorze 3 (Button) i sensor o identyfikatorze 4 (lockSensor S2). Identyfikatory należy wykrywać dynamicznie, a nie zakładać, że są takie same w każdym urządzeniu.

`GET /state` (również `/state/extended`) zwraca `gate.currentPos` oraz tablicę `addons` ze stanami przekaźników, `defaultForTime`, ustawieniem pochwytu i stanem S2.

Zaobserwowane polecenia lokalne dla każdego zgłoszonego wyjścia oświetlenia: `GET /a/{id}/s/0`, `GET /a/{id}/s/1`, `GET /a/{id}/s/1/forTime/{seconds}/ns/0`. Pracę czasową sprawdzono niezależnie dla odpowiednio 10, 4 i 5 sekund. Ustawienie pochwytu korzysta z `GET /a/{id}/s/0` lub `/s/1` dla rozszerzenia settingsSwitch. Ścieżka ustawienia to `settings/gate/conditionalAction/execute`.

S1 jest odczytywany z `gate.currentPos`: 0 oznacza zaryglowanie, 100 — odryglowanie. S1 zmienia się przy użyciu klucza mechanicznego w testowanej instalacji, ale nie potwierdza położenia skrzydła. S2 jest odczytywany z wartości osobnego rozszerzenia sensor; 0 odpowiada odryglowaniu na podstawie wskazania wBox, lecz zmiana stanu i polaryzacja nie zostały niezależnie potwierdzone. Sposób podłączenia zależy od instalacji. Nie należy wnioskować o domknięciu skrzydła wyłącznie na podstawie sygnału rygla.

Przycisk elektrozaczepu wykorzystuje natywną operację otwierania. Jest domyślnie wyłączony; wymaga testu sprzętowego.

Opisane zachowanie dotyczy oprogramowania 0.1060.

## Wejścia fizyczne i akcje

Zweryfikowano dla W-dU-2.0 z oprogramowaniem 0.1060:

- `GET /api/input/state` zwraca `{"inputs":[{"input":0,"state":0},{"input":1,"state":0}]}`. Wpisy odpowiadają poziomom wejść fizycznych; nie zmierzono jeszcze zmian podczas naciskania przycisku ani minimalnej długości impulsu.
- `GET /api/actions/state` zwraca tablicę `actions`, `itemsLimit: 30` i ograniczenia pól.
- Wejście 0 odpowiada IN1 (dzwonek), a wejście 1 — IN2 (pochwyt). Typ wyzwalacza 4 oznacza zbocze narastające.
- Istniejąca akcja natywna: wejście 1, typ wyzwalacza 4, typ akcji 100, parametr `http://localhost/s/p/conditional`. Jest to lokalne warunkowe zwalnianie elektrozaczepu, a nie dowód, że typ 100 jest ogólną akcją URL.
- Typ akcji 52 zaobserwowano dla powiadomienia. Typ 50 zaobserwowano przy zapisywaniu akcji URL w wBox; następnie potwierdzono go, odbierając siedem zdarzeń IN2 w Home Assistancie.
- Puste miejsca mają typ akcji i wyzwalacza 0 oraz pusty parametr. `lastCall.timeElapsedS` to metadane wykonania; dla nieużywanych akcji zaobserwowano -1.

### Zapis pojedynczej akcji

Przechwycony ruch HTTP aplikacji wBox potwierdził żądanie `POST /api/actions/set` z nagłówkiem `Content-Type: application/json`. Poniższy przykład zachowuje zaobserwowaną strukturę żądania, a adres docelowy zastąpiono adresem przeznaczonym do dokumentacji:

```json
{
  "action": {
    "id": 2,
    "name": "HA - HANDLE TEST",
    "input": 0,
    "triggerType": 4,
    "actionType": 50,
    "lastCall": {"timeElapsedS": -1},
    "triggerParam": 0,
    "param": "http://192.0.2.1:8123",
    "throttleS": 0,
    "intervalS": 0
  }
}
```

Sterownik zwrócił HTTP 200 z obiektem `action`; późniejszy odczyt GET potwierdził zmianę wyłącznie miejsca 2. Odpowiedź nie zawierała pola `throttleS`. Nie sprawdzono, czy żądanie może pominąć metadane wykonania lub inne pola. Pomimo nazwy akcji testowej jej wejście miało wartość 0 (IN1).

Należy zachować natywne warunkowe zwalnianie elektrozaczepu i inne akcje użytkownika. Akcje URL zarządzane przez integrację powinny mieć odrębne miejsca, a konfigurację należy zweryfikować odczytem. Potwierdzono dostarczenie zdarzeń IN2 od sterownika do integracji. Dostarczenie IN1, uwierzytelnianie w innych konfiguracjach oraz ograniczenia czasowe krótkich i powtarzanych impulsów wymagają testów. Nieznanego ustawienia pochwytu nie należy traktować jako zezwolenia na odryglowanie.

## Dodatkowe możliwości edytora akcji

Właściciel urządzenia zgłosił, że edytor akcji wBox oferuje zbocze narastające, zmianę stanu, przytrzymanie przycisku, zakończenie przytrzymania, niedomkniętą bramę oraz wyzwalacze nieoczekiwanej akcji. Nie przechwycono niezależnie dokładnej nazwy opcji zmiany stanu ani numerycznych identyfikatorów dodatkowych typów wyzwalaczy. Edytor oferuje także brak akcji, ustawienie stanu, sterowanie innym urządzeniem, wywołanie URL, powiadomienie i powiadomienie niestandardowe. Zgłoszono dwie etykiety związane z URL, których różnicy nie zweryfikowano.

Są to obserwacje interfejsu, a nie potwierdzone mapowania API czy zachowanie sprzętu. Przechwycone zbocze narastające (4) i akcja URL (50) stanowią jedyną kombinację potwierdzoną od początku do końca dla zdarzeń wejściowych HA. Przytrzymanie i zwolnienie przycisku mogłyby umożliwić dodatkowe typy zdarzeń bez odpytywania wejść. Przytrzymanie może również uruchomić istniejącą akcję zbocza narastającego; nie należy zakładać wzajemnego wykluczania gestów ani zmieniać natywnego zwalniania elektrozaczepu. Opcje te nie dowodzą obsługi PWM ani ściemniania.
