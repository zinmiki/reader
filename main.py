
import os
import re
import time
import math
import json
import shutil
import textwrap
import questionary
from rich.live import Live
from rich.layout import Layout
import sys
import select
import termios
import tty

from rich.console import Console
from rich.text import Text

console = Console()

# =========================
# USTAWIENIA
# =========================

SETTINGS = {
    "text": None,
    "time": 60,
    "left": 5,
    "right": 5,
    "top": 1,
    "bottom": 1,
    "color": "green",
    "countdown": 300,
}

CONFIGURATIONS_DIR = "configurations"

NAV_COLOR = "cyan"

COLORS = {
    "Biały": "white",
    "Zielony": "green",
    "Niebieski": "blue",
    "Czerwony": "red",
    "Żółty": "yellow",
    "Cyjan": "cyan",
    "Magenta": "magenta"
}


# =========================
# WYGLĄD
# =========================

def clear():
    console.clear()


def header():
    console.print(
        "[bold cyan]╔═══════════════════════════════════════╗\n"
        "║       PROFESSIONAL TEXT READER        ║\n"
        "╚═══════════════════════════════════════╝[/bold cyan]\n"
    )


# =========================
# WYBÓR PLIKU
# =========================

def select_text():
    files = []

    if os.path.isdir("sources"):
        files = [
            f for f in os.listdir("sources")
            if f.lower().endswith(".txt")
            and os.path.isfile(os.path.join("sources", f))
        ]

    files.sort()

    if not files:
        console.print("[red]Brak plików TXT w katalogu sources/[/red]")
        return

    choice = questionary.select(
        "Wybierz tekst:",
        choices=files,
        default=SETTINGS["text"] if SETTINGS["text"] in files else None
    ).ask()

    if choice and choice:
        SETTINGS["text"] = choice


# =========================
# WYBÓR CZASU
# =========================

def select_time():
    choices = [
        "5 sekund",
        "10 sekund",
        "15 sekund",
        "30 sekund",
        "1 minuta",
        "2 minuty",
        "5 minut",
        "10 minut",
        "Własny czas"
    ]

    times = {
        "5 sekund": 5,
        "10 sekund": 10,
        "15 sekund": 15,
        "30 sekund": 30,
        "1 minuta": 60,
        "2 minuty": 120,
        "5 minut": 300,
        "10 minut": 600
    }

    choice = questionary.select(
        "Czas wyświetlania strony:",
        choices=choices,
        default=next(
            (
                label for label, seconds in times.items()
                if seconds == SETTINGS["time"]
            ),
            "Własny czas"
        )
    ).ask()

    if choice in times:
        SETTINGS["time"] = times[choice]

    elif choice == "Własny czas":
        value = questionary.text(
            "Podaj czas w sekundach:",
            default=str(SETTINGS["time"]),
            validate=lambda x: x.isdigit() and int(x) > 0
        ).ask()

        if value:
            SETTINGS["time"] = int(value)


# =========================
# WYBÓR KOLORU
# =========================

def select_color():
    choice = questionary.select(
        "Wybierz kolor tekstu:",
        choices=list(COLORS.keys()),
        default=next(
            (
                name for name, color in COLORS.items()
                if color == SETTINGS["color"]
            ),
            None
        )
    ).ask()

    if choice:
        SETTINGS["color"] = COLORS[choice]


# =========================
# MARGINESY
# =========================

def select_margins():
    margins = [
        ("left", "Lewy"),
        ("right", "Prawy"),
        ("top", "Górny"),
        ("bottom", "Dolny")
    ]
    sample_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "sample.txt"
    )
    try:
        with open(sample_path, "r", encoding="utf-8") as file:
            sample = file.read()
    except OSError as error:
        console.print(f"[red]Nie można odczytać podglądu: {error}[/red]")
        input("\nEnter...")
        return False

    selected = 0
    pending_value = None
    buffer = ""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setcbreak(fd)
        with Live(
            render_margin_editor(margins, selected, pending_value, sample),
            console=console,
            screen=True,
            refresh_per_second=10,
            transient=True
        ) as live:
            while True:
                live.update(
                    render_margin_editor(
                        margins,
                        selected,
                        pending_value,
                        sample
                    )
                )
                if not select.select([sys.stdin], [], [], 0.05)[0]:
                    continue

                buffer += os.read(fd, 32).decode("ascii", errors="ignore")

                while buffer:
                    if buffer.startswith("\x1b["):
                        if len(buffer) < 3:
                            break
                        key, buffer = buffer[:3], buffer[3:]
                        if key == "\x1b[A":
                            side = margins[selected][0]
                            SETTINGS[side] += 1
                            pending_value = None
                        elif key == "\x1b[B":
                            side = margins[selected][0]
                            SETTINGS[side] = max(0, SETTINGS[side] - 1)
                            pending_value = None
                        elif key == "\x1b[C":
                            selected = (selected + 1) % len(margins)
                            pending_value = None
                        elif key == "\x1b[D":
                            selected = (selected - 1) % len(margins)
                            pending_value = None
                        continue

                    if buffer == "\x1b":
                        if select.select([sys.stdin], [], [], 0.02)[0]:
                            buffer += os.read(fd, 32).decode(
                                "ascii",
                                errors="ignore"
                            )
                            continue
                        return False

                    key, buffer = buffer[0], buffer[1:]
                    if key in ("\r", "\n", "q", "Q"):
                        return True
                    if key in ("\x7f", "\b"):
                        if pending_value:
                            pending_value = pending_value[:-1]
                            side = margins[selected][0]
                            SETTINGS[side] = int(pending_value or "0")
                    elif key.isdigit():
                        pending_value = (
                            (pending_value or "") + key
                        )
                        side = margins[selected][0]
                        SETTINGS[side] = int(pending_value)
                    elif key in ("+", "="):
                        side = margins[selected][0]
                        SETTINGS[side] += 1
                        pending_value = None
                    elif key == "-":
                        side = margins[selected][0]
                        SETTINGS[side] = max(0, SETTINGS[side] - 1)
                        pending_value = None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def render_margin_editor(margins, selected, pending_value, sample):
    content_width = max(
        0,
        console.size.width - SETTINGS["left"] - SETTINGS["right"]
    )
    preview_height = max(1, console.size.height - 3)

    left = SETTINGS["left"]
    right = SETTINGS["right"]
    sample_lines = []
    for line in sample.splitlines():
        if not line:
            sample_lines.append("")
        elif content_width:
            sample_lines.extend(
                textwrap.wrap(line, width=content_width) or [""]
            )

    top = min(SETTINGS["top"], preview_height)
    bottom = min(
        max(0, SETTINGS["bottom"] - 2),
        preview_height - top
    )
    text_rows = max(0, preview_height - top - bottom)
    visible_lines = sample_lines[:text_rows]
    lines = [Text() for _ in range(top)]

    for line in visible_lines:
        rendered_line = Text(" " * left)
        rendered_line.append(line, style=SETTINGS["color"])
        rendered_line.append(" " * right)
        lines.append(rendered_line)

    lines.extend(Text() for _ in range(text_rows - len(visible_lines)))
    lines.extend(Text() for _ in range(bottom))

    preview = Text("\n").join(lines)
    controls = Text.assemble(
        ("←/→ ", "bold cyan"),
        "wybór marginesu  ",
        ("↑/↓ ", "bold cyan"),
        "zmiana o 1  ",
        ("cyfry ", "bold cyan"),
        "wpisanie wartości  ",
        ("Enter/Q ", "bold cyan"),
        "gotowe  ",
        ("Esc ", "bold cyan"),
        "anuluj\n",
        *[
            (
                f"{'▶ ' if index == selected else ''}"
                f"{label}: {SETTINGS[side]}"
                f"{' (' + pending_value + ')' if index == selected and pending_value else ''}"
                f"{'    ' if index < len(margins) - 1 else ''}",
                "bold yellow" if index == selected else "dim"
            )
            for index, (side, label) in enumerate(margins)
        ]
    )

    layout = Layout()
    layout.split_column(
        Layout(
            Text("USTAWIANIE MARGINESÓW", style="bold cyan"),
            name="header",
            size=1
        ),
        Layout(preview, name="preview", ratio=1),
        Layout(controls, name="controls", size=2)
    )
    return layout


def validate_configuration(configuration):
    if not isinstance(configuration, dict):
        raise ValueError("Konfiguracja musi być obiektem JSON.")

    missing = set(SETTINGS) - configuration.keys()
    if missing:
        raise ValueError(
            "Brak wymaganych pól: " + ", ".join(sorted(missing))
        )

    text = configuration["text"]
    if (
        not isinstance(text, str)
        or os.path.basename(text) != text
        or not text.lower().endswith(".txt")
        or not os.path.isfile(os.path.join("sources", text))
    ):
        raise ValueError("Wybrany plik tekstowy nie istnieje w sources/.")

    for key in ("time", "countdown", "left", "right", "top", "bottom"):
        value = configuration[key]
        minimum = 1 if key == "time" else 0
        if type(value) is not int or value < minimum:
            raise ValueError(f"Nieprawidłowa wartość pola „{key}”.")

    if configuration["color"] not in COLORS.values():
        raise ValueError("Nieprawidłowy kolor tekstu.")


def saved_configurations():
    if not os.path.isdir(CONFIGURATIONS_DIR):
        return []

    return sorted(
        filename for filename in os.listdir(CONFIGURATIONS_DIR)
        if filename.lower().endswith(".json")
        and os.path.isfile(os.path.join(CONFIGURATIONS_DIR, filename))
    )


def load_configuration(filename):
    path = os.path.join(CONFIGURATIONS_DIR, filename)

    try:
        with open(path, "r", encoding="utf-8") as file:
            configuration = json.load(file)

        validate_configuration(configuration)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        console.print(f"[red]Nie można wczytać konfiguracji: {error}[/red]")
        input("\nEnter...")
        return False

    SETTINGS.update({key: configuration[key] for key in SETTINGS})
    console.print(f"[green]Wczytano konfigurację: {filename}[/green]")
    return True


def save_configuration():
    name = questionary.text(
        "Nazwa konfiguracji:",
        validate=lambda value: bool(
            value.strip()
            and all(
                character.isalnum() or character in " _-"
                for character in value.strip()
            )
        )
    ).ask()

    if name is None:
        return

    filename = name.strip() + ".json"
    path = os.path.join(CONFIGURATIONS_DIR, filename)

    if os.path.exists(path):
        overwrite = questionary.confirm(
            f"Konfiguracja „{filename}” już istnieje. Nadpisać?",
            default=False
        ).ask()
        if overwrite is not True:
            return

    try:
        validate_configuration(SETTINGS)
        os.makedirs(CONFIGURATIONS_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(SETTINGS, file, ensure_ascii=False, indent=2)
    except (OSError, ValueError) as error:
        console.print(f"[red]Nie można zapisać konfiguracji: {error}[/red]")
        input("\nEnter...")
        return

    console.print(f"[green]Zapisano konfigurację: {path}[/green]")


# =========================
# MARKDOWN
# =========================

def parse_inline(content, base_style):
    """
    Obsługa podstawowego formatowania Markdown.
    Zwraca obiekt Rich Text.
    """

    result = Text()

    pattern = re.compile(
        r'(\*\*.+?\*\*|__.+?__|~~.+?~~|'
        r'\*.+?\*|_.+?_|`.+?`|'
        r'\[.+?\]\(.+?\))'
    )

    position = 0

    for match in pattern.finditer(content):
        # Zwykły tekst
        result.append(
            content[position:match.start()],
            style=base_style
        )

        token = match.group()
        value = token

        if token.startswith("**") and token.endswith("**"):
            value = token[2:-2]
            result.append(value, style=f"{base_style} bold")

        elif token.startswith("__") and token.endswith("__"):
            value = token[2:-2]
            result.append(value, style=f"{base_style} bold")

        elif token.startswith("~~") and token.endswith("~~"):
            value = token[2:-2]
            result.append(value, style=f"{base_style} strike")

        elif token.startswith("*") and token.endswith("*"):
            value = token[1:-1]
            result.append(value, style=f"{base_style} italic")

        elif token.startswith("_") and token.endswith("_"):
            value = token[1:-1]
            result.append(value, style=f"{base_style} italic")

        elif token.startswith("`") and token.endswith("`"):
            value = token[1:-1]
            result.append(
                value,
                style="bold yellow on grey11"
            )

        elif token.startswith("["):
            link = re.match(r'\[(.*?)\]\((.*?)\)', token)

            if link:
                result.append(
                    link.group(1),
                    style=f"{base_style} underline"
                )
            else:
                result.append(token, style=base_style)

        else:
            result.append(token, style=base_style)

        position = match.end()

    result.append(content[position:], style=base_style)

    return result


def parse_markdown(line):
    """
    Przetwarza pojedynczą linię Markdown.
    """

    line = line.rstrip("\r")

    base_color = SETTINGS["color"]

    # Nagłówki
    heading = re.match(r'^(#{1,3})\s+(.*)$', line)

    if heading:
        level = len(heading.group(1))
        content = heading.group(2)

        prefix = {
            1: ">>> ",
            2: ">> ",
            3: "> "
        }[level]

        # Jeśli podstawowy kolor to biały,
        # nagłówki będą zielone.
        heading_color = (
            "green" if base_color == "white"
            else "white"
        )

        result = Text(prefix, style=f"bold {heading_color}")
        result.append_text(
            parse_inline(content, f"bold {heading_color}")
        )

        return result

    # Cytat
    if line.startswith("> "):
        result = Text("│ ", style="cyan")
        result.append_text(
            parse_inline(line[2:], f"italic {base_color}")
        )
        return result

    # Lista punktowana
    if line.startswith("- ") or line.startswith("* "):
        result = Text("• ", style="bold cyan")
        result.append_text(
            parse_inline(line[2:], base_color)
        )
        return result

    # Lista numerowana
    numbered = re.match(r'^(\d+)\.\s+(.*)$', line)

    if numbered:
        result = Text(
            numbered.group(1) + ". ",
            style="bold cyan"
        )
        result.append_text(
            parse_inline(numbered.group(2), base_color)
        )
        return result

    # Pozioma linia
    if line.strip() in ("---", "***", "___"):
        return Text("─" * 20, style="dim")

    # Zwykły tekst
    return parse_inline(line, base_color)


# =========================
# PRZYGOTOWANIE STRON
# =========================

def prepare_pages(content):
    width, height = shutil.get_terminal_size()

    left = SETTINGS["left"]
    right = SETTINGS["right"]

    usable_width = max(1, width - left - right)

    # Jedna linia na nawigację!
    usable_height = max(
        1,
        height - SETTINGS["top"] - SETTINGS["bottom"] - 1
    )

    lines = []

    for raw_line in content.splitlines():
        parsed = parse_markdown(raw_line)

        wrapped = parsed.wrap(
            console,
            width=usable_width,
            overflow="fold",
            no_wrap=False
        )

        if not wrapped:
            lines.append(Text())
        else:
            lines.extend(wrapped)

    # Podział na strony
    pages = []

    for i in range(0, len(lines), usable_height):
        pages.append(lines[i:i + usable_height])

    return pages, width, height


# =========================
# KOLOR NAWIGACJI
# =========================

def get_navigation_color(remaining):
    if remaining <= 5:
        return "bold red"

    elif remaining <= 10:
        return "bold yellow"

    return f"bold {NAV_COLOR}"


# =========================
# WYŚWIETLANIE STRONY
# =========================

def render_page(page, pages, remaining, width):
    navigation = (
        f"{page + 1:03d} "
        f"Page: {page + 1}/{len(pages)} "
        f": T: {remaining}s "
    )

    navigation += "-" * max(0, width - len(navigation))
    navigation = navigation[:width]

    nav = Text(
        navigation,
        style=get_navigation_color(remaining),
        no_wrap=True
    )

    content = Text()

    for _ in range(SETTINGS["top"]):
        content.append("\n")

    for line in pages[page]:
        content.append(" " * SETTINGS["left"])
        content.append_text(line)
        content.append("\n")

    for _ in range(SETTINGS["bottom"]):
        content.append("\n")

    result = Text()
    result.append_text(nav)
    result.append("\n")
    result.append_text(content)

    return result


# =========================
# URUCHOMIENIE TEKSTU
# =========================

from contextlib import contextmanager

@contextmanager
def mouse_support():
    """
    Włącza obsługę kliknięć myszy w terminalu.
    Obsługuje terminale zgodne z SGR Mouse.
    """

    if os.name != "posix" or not sys.stdin.isatty():
        yield lambda: False
        return

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    buffer = ""

    def poll_click():
        nonlocal buffer

        clicked = False

        while select.select([sys.stdin], [], [], 0)[0]:
            data = os.read(fd, 128).decode("latin1")
            buffer += data

        # Odczyt sekwencji kliknięcia myszy
        pattern = re.compile(
            r"\x1b\[<(\d+);(\d+);(\d+)([mM])"
        )

        for match in pattern.finditer(buffer):
            button = int(match.group(1))
            event = match.group(4)

            # Lewy przycisk myszy, bez ruchu kursora
            if event == "M" and (button & 3) == 0 and not (button & 32):
                clicked = True

        # Usuwamy przetworzone sekwencje
        buffer = pattern.sub("", buffer)

        # Ograniczenie bufora
        if len(buffer) > 256:
            buffer = buffer[-64:]

        return clicked

    try:
        tty.setcbreak(fd)

        # Włączenie raportowania kliknięć
        sys.stdout.write("\033[?1000h")
        sys.stdout.write("\033[?1006h")
        sys.stdout.flush()

        yield poll_click

    finally:
        # Wyłączenie obsługi myszy
        sys.stdout.write("\033[?1000l")
        sys.stdout.write("\033[?1006l")
        sys.stdout.flush()

        termios.tcsetattr(
            fd,
            termios.TCSADRAIN,
            old_settings
        )




def show_pages(test_mode=False):
    if not SETTINGS["text"]:
        console.print("[red]Najpierw wybierz plik tekstowy![/red]")
        input("\nEnter...")
        return

    path = os.path.join("sources", SETTINGS["text"])

    try:
        with open(path, "r", encoding="utf-8") as file:
            content = file.read()

    except OSError as e:
        console.print(f"[red]Błąd odczytu: {e}[/red]")
        input("\nEnter...")
        return

    try:
        if not test_mode:
            start_countdown()
        else:
            time.sleep(3)

        pages, width, height = prepare_pages(content)

        if not pages:
            pages = [[Text()]]

        page = 0
        duration = 10 if test_mode else SETTINGS["time"]

        # Włączenie myszy
        with mouse_support() as poll_click:

            with Live(
                console=console,
                screen=True,
                refresh_per_second=10,
                transient=True
            ) as live:

                while True:
                    start = time.monotonic()
                    previous_remaining = None

                    while True:
                        elapsed = time.monotonic() - start

                        remaining = max(
                            0,
                            math.ceil(duration - elapsed)
                        )

                        # Aktualizacja licznika
                        if remaining != previous_remaining:

                            display = render_page(
                                page,
                                pages,
                                remaining,
                                width
                            )

                            live.update(display)

                            previous_remaining = remaining

                        # Kliknięcie myszy = następna strona
                        if poll_click() and not test_mode:
                            break

                        # Koniec czasu = następna strona
                        if elapsed >= duration:
                            break

                        time.sleep(0.05)

                    if test_mode:
                        break

                    # Następna strona
                    page += 1

                    if page >= len(pages):
                        page = 0

    except KeyboardInterrupt:
        pass

    clear()
    console.print("[yellow]Zakończono wyświetlanie.[/yellow]")



# =======
# start culdown

#

def start_countdown():
    seconds = SETTINGS["countdown"]

    if seconds <= 0:
        return

    with Live(
        console=console,
        screen=True,
        refresh_per_second=1
    ) as live:
        for remaining in range(seconds, 0, -1):
            display = Text()
            if (remaining > 99):
                if remaining % 2:
                    display.append(
                        f".",
                        style="bold green"
                    )
                else:
                    display.append(
                        f".",
                        style="bold yellow"
                    )
            else:
                display.append(
                    f"\n\n                       {remaining}s",
                    style="bold white"
                )

            live.update(display)
            time.sleep(1)


# =========================
# MENU GŁÓWNE
# =========================

def configure_settings():
    # 1. Wybór tekstu
    select_text()

    if not SETTINGS["text"]:
        return False

    # 2. Czas
    time_choices = [
        questionary.Choice("15 sekund", 15),
        questionary.Choice("30 sekund", 30),
        questionary.Choice("1 minuta", 60),
        questionary.Choice("1.5 minuty", 90),
        questionary.Choice("2 minuty", 120),
        questionary.Choice("Własny czas", -1)
    ]
    value = questionary.select(
        "Ile sekund ma być wyświetlana jedna strona?",
        choices=time_choices,
        default=(
            SETTINGS["time"]
            if SETTINGS["time"] in (15, 30, 60, 90, 120)
            else -1
        )
    ).ask()

    if value is None:
        return False

    if value == -1:
        custom = questionary.text(
            "Czas wyświetlania strony:",
            default=str(SETTINGS["time"]),
            validate=lambda x: x.isdigit() and int(x) > 0
        ).ask()

        if custom is None:
            return False

        SETTINGS["time"] = int(custom)
    else:
        SETTINGS["time"] = value

    # 3. Marginesy
    if not select_margins():
        return False

    # 4. Kolor
    select_color()

    # Opóźnienie startu
    countdown_choices = [
        questionary.Choice("Bez opóźnienia", 0),
        questionary.Choice("1 minuta", 60),
        questionary.Choice("2 minuty", 120),
        questionary.Choice("3 minuty", 180),
        questionary.Choice("5 minuty", 300),
        questionary.Choice("10 minuty", 600),
        questionary.Choice("Własny czas", -1)
    ]
    value = questionary.select(
        "Ile sekund odliczać przed uruchomieniem?",
        choices=countdown_choices,
        default=(
            SETTINGS["countdown"]
            if SETTINGS["countdown"] in (0, 60, 120, 180, 300, 600)
            else -1
        )
    ).ask()

    if value is None:
        return False

    if value == -1:
        custom = questionary.text(
            "Podaj opóźnienie w sekundach:",
            default=str(SETTINGS["countdown"]),
            validate=lambda x: x.isdigit()
        ).ask()

        if custom is None:
            return False

        SETTINGS["countdown"] = int(custom)
    else:
        SETTINGS["countdown"] = value

    return True


def show_configuration_summary():
    clear()
    header()

    console.print("[bold cyan]PODSUMOWANIE USTAWIEŃ[/bold cyan]\n")
    console.print(f"Tekst:       [green]{SETTINGS['text']}[/green]")
    console.print(f"Czas:        {SETTINGS['time']} sekund")
    console.print(f"Margines L:  {SETTINGS['left']}")
    console.print(f"Margines R:  {SETTINGS['right']}")
    console.print(f"Margines G:  {SETTINGS['top']}")
    console.print(f"Margines D:  {SETTINGS['bottom']}")
    console.print(f"Kolor:       [{SETTINGS['color']}]{SETTINGS['color']}[/]")
    console.print(f"Opóźnienie:  {SETTINGS['countdown']} sekund\n")


def configure(reuse_configuration=False):
    if not reuse_configuration:
        clear()
        header()

        console.print("[bold cyan]KONFIGURACJA PROGRAMU[/bold cyan]\n")

        choices = [
            questionary.Choice(filename, filename)
            for filename in saved_configurations()
        ]
        choices.append(questionary.Choice("+ Nowa konfiguracja", "__new__"))

        mode = questionary.select(
            "Wybierz konfigurację:",
            choices=choices
        ).ask()

        if mode is None:
            return "exit"

        if mode != "__new__":
            if not load_configuration(mode):
                return "exit"
        elif not configure_settings():
            return "exit"

    while True:
        show_configuration_summary()
        action = questionary.select(
            "Wybierz dostępną opcję",
            choices=[
                questionary.Choice("Gotowość", "ready"),
                questionary.Choice("Test", "test"),
                questionary.Choice("Zmień", "change"),
                questionary.Choice("Zapisz", "save"),
                questionary.Choice("Wyjdź", "exit")
            ]
        ).ask()

        if action in ("ready", "test", "exit") or action is None:
            return action or "exit"

        if action == "change":
            if not configure_settings():
                return "exit"
        elif action == "save":
            save_configuration()


def main():
    reuse_configuration = False

    while True:
        try:
            action = configure(reuse_configuration)
            if action == "exit":
                break

            if action == "test":
                show_pages(test_mode=True)
                reuse_configuration = True
                continue

            show_pages()
            reuse_configuration = False

            again = questionary.confirm(
                "Czy skonfigurować i uruchomić ponownie?",
                default=True
            ).ask()

            if not again:
                break

        except KeyboardInterrupt:
            break

    console.print("[bold red]Zakończono program![/bold red]")


if __name__ == "__main__":
    main()
