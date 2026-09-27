#!/usr/bin/env bash
# ABOUTME: Installs the Prusawire demo G-code and loop macros into Klipper's printer_data on the Pi.
# ABOUTME: Asks YES/no before each step; set PRINTER_DATA to use a folder other than ~/printer_data.

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRINTER_DATA="${PRINTER_DATA:-$HOME/printer_data}"
GCODES_DIR="$PRINTER_DATA/gcodes"
CONFIG_DIR="$PRINTER_DATA/config"
DEMO_CFG="prusawire_demo.cfg"
INCLUDE_LINE="[include $DEMO_CFG]"

failed=0
needs_restart=0

# Ask a YES/no question. Enter, y or yes (any case) means yes; so does end of input.
ask() {
    local answer
    printf '%s [Y/n] ' "$1"
    if ! read -r answer; then
        echo
        return 0
    fi
    answer="$(printf '%s' "$answer" | tr '[:upper:]' '[:lower:]')"
    [ -z "$answer" ] || [ "$answer" = "y" ] || [ "$answer" = "yes" ]
}

install_gcode() {
    if [ ! -d "$GCODES_DIR" ]; then
        echo "  ERROR: gcodes folder not found: $GCODES_DIR"
        failed=1
        return
    fi
    local count=0 file
    for file in "$REPO_DIR"/gcode/*.gcode; do
        cp "$file" "$GCODES_DIR/" || { failed=1; return; }
        count=$((count + 1))
    done
    echo "  Copied $count demo files to $GCODES_DIR"
}

install_demo_cfg() {
    if [ ! -d "$CONFIG_DIR" ]; then
        echo "  ERROR: config folder not found: $CONFIG_DIR"
        failed=1
        return
    fi
    cp "$REPO_DIR/$DEMO_CFG" "$CONFIG_DIR/" || { failed=1; return; }
    needs_restart=1
    echo "  Copied $DEMO_CFG to $CONFIG_DIR"
}

# Adds the include at the top of printer.cfg so it never lands inside
# Klipper's SAVE_CONFIG block at the end of the file.
add_include() {
    local printer_cfg="$CONFIG_DIR/printer.cfg"
    if [ ! -f "$printer_cfg" ]; then
        echo "  ERROR: printer.cfg not found: $printer_cfg"
        failed=1
        return
    fi
    if grep -Eq "^[[:space:]]*\[include[[:space:]]+$DEMO_CFG[[:space:]]*\]" "$printer_cfg"; then
        echo "  printer.cfg already includes $DEMO_CFG - nothing to do"
        return
    fi
    if [ ! -f "$CONFIG_DIR/$DEMO_CFG" ]; then
        echo "  Skipped: $DEMO_CFG is not in $CONFIG_DIR, and including it would stop Klipper from starting."
        return
    fi
    local backup
    backup="$printer_cfg.bak-$(date +%Y%m%d-%H%M%S)"
    cp "$printer_cfg" "$backup" || { failed=1; return; }
    { echo "$INCLUDE_LINE"; cat "$backup"; } > "$printer_cfg" || { failed=1; return; }
    needs_restart=1
    echo "  Added $INCLUDE_LINE to the top of printer.cfg (backup: $(basename "$backup"))"
}

echo "Prusawire demo installer - printer_data: $PRINTER_DATA"
echo

if ask "1/3 Copy demo G-code files to $GCODES_DIR?"; then
    install_gcode
fi
if ask "2/3 Copy $DEMO_CFG (DEMO_LOOP macros) to $CONFIG_DIR?"; then
    install_demo_cfg
fi
if ask "3/3 Add $INCLUDE_LINE to printer.cfg?"; then
    add_include
fi

echo
if [ "$needs_restart" -eq 1 ]; then
    echo "Restart Klipper to load the macros: FIRMWARE_RESTART in the Mainsail console,"
    echo "or: sudo systemctl restart klipper"
fi
if [ "$failed" -ne 0 ]; then
    echo "Finished with errors - see above."
    exit 1
fi
echo "Done."
