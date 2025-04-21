# Implementacja protokołu Xmodem w języku Python

Ten program implementuje protokół transferu plików `Xmodem` z wykorzystaniem API Windows

---

## Czym jest Xmodem?

**Xmodem** to jeden z najwcześniejszych protokołów używanych do transferów plików przez porty szeregowe (np. RS-232) 

---

## Zasada działania

1. **Odbiorca inicjuje połączenie**
   - Wysyła `NAK` (dla trybu sumy kontrolnej) lub `C` (dla trybu CRC), aby zasygnalizować, że jest gotowy do odbierania danych.

2. **Nadawca zaczyna przesyłać pakiety**
   - Każdy pakiet zawiera:
   ```
   [SOH][Numer bloku][255 - Numer bloku][128 bajtów danych][Suma kontrolna/CRC]
   ```
   - Jeżeli odbiorca znajdzie błąd w bloku, wysyła `NAK`, aby zasygnalizować prośbę o ponowne wysłanie pakietu
   - Jeżeli blok jest poprawny, wysyła `ACK`, aby zasygnalizować prośbę o następny blok

3. **Zakończenie transmisji**
   - Po odebraniu `ACK` po wysłaniu ostatniego pakietu, nadawca wysyła `EOT`, aby zasygnalizować koniec transmisji
   - Odbiorca odpowiada wysyłając `ACK`

---

## Opis implementacji

- Program został napisany w języku Python z wykorzystaniem `ctypes` do komunikacji z API Windowsa
- Obsługuje wykrywanie błędów za pomocą **sumy kontrolnej** lub **CRC**
- Używa pakietów o rozmiarze 128 bajtów

### Kluczowe wartości

| Wartość      | Opis                                                                                                                                    |
|--------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| `SOH` (0x01) | Początek Nagłówka (Start of Header), oznacza początek pakietu                                                                           |
| `EOT` (0x04) | Koniec Transmisji (End of Transmission), używany do zakończenia połączenia                                                              |
| `ACK` (0x06) | Potwierdzenie (Acknowledge), używany aby potwierdzić odebrany blok                                                                      |
| `NAK` (0x15) | Odrzucenie (Negative Acknowledge), używany do rozpoczęcia transferu w trybie sumy kontrolnej oraz do odrzucenia pakietu                 |
| `CAN` (0x18) | Anulowanie transmisji (Cancel Transfer), w razie wystąpienia błędu wysyłany jest aby sygnalizować natychmiastowe zakończenie połączenia |
| `C`          | Używany do zainicjowania transmisji w trybie CRC                                                                                        |

### Sprawdzanie błędów

- **Suma kontrolna** (checksum) - suma bajtów wszystkich danych modulo 256
- **CRC** - używa CRC-16-CCITT (wielomian `0x1021`)

### Wymagania

- System Windows
- Python 3.11 lub nowszy
- Port szeregowy (fizyczny lub emulowany, np. `com0com`)
- Urządzenie obsługujące port szeregowy (np. `Tera Term`)

### Struktura plików

| Plik              | Zastosowanie                                                                 |
|-------------------|------------------------------------------------------------------------------|
| `main.py`         | Interaktywny interfejs od wykorzystania protokołu Xmodem z użyciem terminala |
| `Xmodem.py`       | Implementacja protokołu Xmodem                                               |
| `dcb.py`          | Struktura DCB do konfiguracji portów szeregowych                             |
| `commtimeouts.py` | Struktura COMMTIMEOUTS do konfiguracji limitów czasu                         |

### Uruchamianie

Aby rozpocząć, wykonaj `python main.py`.  
Program poprowadzi Cię krok po kroku przez wybór portu, pliku i trybu transmisji.

---

## Dodatkowe informacje

### Jak zainstalować `com0com`?

Link do pobrania: [com0com](https://sourceforge.net/projects/com0com/)

Po zainstalowaniu należy otworzyć Windows Update i przejść do:  
Aktualizacje opcjonalne -> Aktualizacje sterowników -> Vyacheslav Frolov - Ports  
Instalujemy sterownik i uruchamiamy ponownie system  
Teraz w aplikacji Setup od com0com możemy utworzyć nowy wirtualny port szeregowy  

### Jak używać `Tera Term`?

Link do pobrania: [Tera Term](https://github.com/TeraTermProject/teraterm/releases)

Po uruchomieniu programu otworzy się okno terminala oraz okno tworzenia połączenia.  
Wybieramy Serial oraz port, do którego chcemy się połączyć.  
W terminalu wpisywanie znaków nie wyświetli ich na ekranie, jednak dane będą przesyłane.  

#### Wysyłanie plików z użyciem Xmodem

File -> Transfer -> XMODEM -> Send...
Teraz wybieramy plik, który chcemy wysłać

#### Odbieranie plików z użyciem Xmodem

File -> Transfer -> XMODEM -> Receive...
Teraz wybieramy plik, który chcemy odebrać.
Dodatkowo na samym dole okna możemy wybrać tryb sumy kontrolnej