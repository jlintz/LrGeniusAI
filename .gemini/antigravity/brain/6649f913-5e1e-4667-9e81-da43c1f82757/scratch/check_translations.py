import os
import re

def get_translations(file_path):
    translations = {}
    if not os.path.exists(file_path):
        return translations
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            # Match "$$$/key=Value" or "$$$/key"
            match = re.search(r'"\$\$\$(.*?)"', line)
            if match:
                content = match.group(1)
                if '=' in content:
                    key, val = content.split('=', 1)
                else:
                    key = content
                    val = ""
                translations[key] = val
    return translations

def get_loc_keys(directory):
    keys = {}
    # Search for LOC "$$$/...
    # Pattern to match key and optional default value: LOC "$$$/key=default"
    pattern = re.compile(r'LOC\s*\(?\s*["\']\$\$\$(.*?)["\']')
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.lua'):
                with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    matches = pattern.findall(content)
                    for m in matches:
                        if '=' in m:
                            key, val = m.split('=', 1)
                        else:
                            key = m
                            val = ""
                        if key not in keys:
                            keys[key] = []
                        keys[key].append((file, val))
    return keys

def find_raw_strings(directory):
    # This is hard because many strings are technical (IDs, filenames, etc).
    # But strings in LrDialogs calls are likely GUI strings.
    raw_dialogs = []
    # Pattern for LrDialogs.confirm( "string", "string", ... )
    # This is a bit complex, let's just look for strings in common dialog calls
    pattern = re.compile(r'LrDialogs\.(confirm|message|showModalDialog|promptForKeys|promptForTargetPhoto)\s*\((.*?)\)', re.DOTALL)
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.lua'):
                with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    for call_type, args in pattern.findall(content):
                        # Find strings in args that don't start with LOC "$$$/
                        # This is very approximate
                        strings = re.findall(r'["\'](.*?)["\']', args)
                        for s in strings:
                            if s.strip() and not s.startswith('$$$/') and not s.startswith('http') and len(s) > 3:
                                # Likely a raw string
                                if s not in ["ok", "cancel", "info", "critical", "warning"]:
                                    raw_dialogs.append((file, call_type, s))
    return raw_dialogs

def main():
    plugin_dir = 'plugin/LrGeniusAI.lrdevplugin'
    en_path = os.path.join(plugin_dir, 'TranslatedStrings_en.txt')
    de_path = os.path.join(plugin_dir, 'TranslatedStrings_de.txt')
    fr_path = os.path.join(plugin_dir, 'TranslatedStrings_fr.txt')

    en_trans = get_translations(en_path)
    de_trans = get_translations(de_path)
    fr_trans = get_translations(fr_path)

    loc_keys = get_loc_keys('plugin')
    raw_strings = find_raw_strings('plugin')

    results = []
    results.append("# Translation Analysis Results\n")

    results.append("## Summary")
    results.append(f"- Total unique LOC keys found in code: {len(loc_keys)}")
    results.append(f"- EN keys in file: {len(en_trans)}")
    results.append(f"- DE keys in file: {len(de_trans)}")
    results.append(f"- FR keys in file: {len(fr_trans)}")
    results.append(f"- Potential raw GUI strings found: {len(raw_strings)}\n")

    all_keys = set(loc_keys.keys()).union(en_trans.keys()).union(de_trans.keys()).union(fr_trans.keys())

    missing_in_en = []
    missing_in_de = []
    missing_in_fr = []
    de_is_english = []
    fr_is_english = []

    for key in sorted(all_keys):
        # Missing translations
        if key not in en_trans:
            missing_in_en.append(key)
        if key not in de_trans:
            missing_in_de.append(key)
        if key not in fr_trans:
            missing_in_fr.append(key)

        # Un-translated but present (value matches English)
        if key in en_trans:
            en_val = en_trans[key]
            if not en_val and key in loc_keys:
                en_val = loc_keys[key][0][1] # Use default from code if available
            
            if en_val:
                if key in de_trans and de_trans[key] == en_val and en_val.strip() != "":
                    de_is_english.append((key, en_val))
                if key in fr_trans and fr_trans[key] == en_val and en_val.strip() != "":
                    fr_is_english.append((key, en_val))

    results.append("## Missing in EN (Keys in code but not in TranslatedStrings_en.txt)")
    count = 0
    for k in missing_in_en:
        if k in loc_keys:
             results.append(f"- `{k}` (Default in code: \"{loc_keys[k][0][1]}\")")
             count += 1
    if count == 0: results.append("None")

    results.append("\n## Missing in DE")
    count = 0
    for k in missing_in_de:
        if k in loc_keys or k in en_trans:
            results.append(f"- `{k}`")
            count += 1
    if count == 0: results.append("None")

    results.append("\n## Missing in FR")
    count = 0
    for k in missing_in_fr:
        if k in loc_keys or k in en_trans:
            results.append(f"- `{k}`")
            count += 1
    if count == 0: results.append("None")

    results.append("\n## DE Still English (Value matches EN)")
    if not de_is_english:
        results.append("None")
    for k, v in de_is_english:
        results.append(f"- `{k}` = \"{v}\"")

    results.append("\n## FR Still English (Value matches EN)")
    if not fr_is_english:
        results.append("None")
    for k, v in fr_is_english:
        results.append(f"- `{k}` = \"{v}\"")

    results.append("\n## Potential Raw Strings (Hardcoded in LrDialogs)")
    if not raw_strings:
        results.append("None")
    for file, call, s in raw_strings:
        results.append(f"- **{file}**: {call}(\"{s}\")")

    results.append("\n## Dead Keys (In translation files but not found in code)")
    # This might have false positives if keys are dynamic
    count = 0
    for key in sorted(all_keys):
        if key not in loc_keys and not key.startswith('$$$/'):
             # If it doesn't even look like a key, skip
             continue
        if key not in loc_keys:
             results.append(f"- `{key}`")
             count += 1
    if count == 0: results.append("None")

    with open('translation_results.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))
    print("Results written to translation_results.md")

if __name__ == "__main__":
    main()
