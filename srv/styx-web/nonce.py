import os
import re
import base64

def generate_nonce():
    return base64.b64encode(os.urandom(16)).decode('utf-8')

def add_nonce_to_script_tags(html_content, nonce):
    # Add the nonce only once per script tag
    return re.sub(r'(<script)([^>]*)>', rf'\1 nonce="{nonce}"\2>', html_content)

def update_csp_with_nonce(html_content, nonce):
    # Adjust the script-src directive to include the nonce
    csp_pattern = r"(Content-Security-Policy[^;]*)(script-src [^;]*)"
    nonce_csp = f" 'nonce-{nonce}'"
    return re.sub(csp_pattern, rf"\1\2{nonce_csp}", html_content)

def process_html_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as file:
        content = file.read()

    nonce = generate_nonce()  # Generate a single nonce for this HTML file
    content_with_nonce = add_nonce_to_script_tags(content, nonce)
    content_with_csp = update_csp_with_nonce(content_with_nonce, nonce)

    with open(filepath, 'w', encoding='utf-8') as file:
        file.write(content_with_csp)

def process_directory(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".html"):
                process_html_file(os.path.join(root, file))

if __name__ == "__main__":
    html_directory = "/srv/styx-web/html/4.1"
    process_directory(html_directory)
