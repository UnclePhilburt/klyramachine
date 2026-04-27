#!/bin/bash
# Compile Python code to bytecode and remove source

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "🔒 Compiling Python code to bytecode..."

# Compile all Python files to bytecode
python3 -m compileall "$SCRIPT_DIR"

# Create backup of source files (optional)
BACKUP_DIR="$SCRIPT_DIR/source_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp *.py "$BACKUP_DIR/" 2>/dev/null

echo "✓ Python files compiled to .pyc"
echo ""
echo "⚠️  WARNING: This will delete the source .py files!"
echo "Backup created at: $BACKUP_DIR"
echo ""
read -p "Delete source .py files? (yes/no): " confirm

if [ "$confirm" = "yes" ]; then
    # Remove source files, keep only bytecode
    rm -f *.py
    echo "✓ Source files removed. Only bytecode remains."
    echo ""
    echo "Note: Bytecode can still be decompiled but it's harder."
else
    echo "Cancelled. Source files kept."
fi
