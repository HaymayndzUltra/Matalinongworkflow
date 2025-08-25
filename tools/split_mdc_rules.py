#!/usr/bin/env python3
"""
MDC Rules File Splitter

Splits a large .mdc file containing multiple rule prompts into individual .mdc files
with proper frontmatter and sensible globs.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

# Mapping for technology detection and file organization
MAPPING = {
    'python': {'bucket': 'language/python', 'globs': '**/*.py', 'base': 'python-general'},
    'django': {'bucket': 'framework/django', 'globs': '**/*.py', 'base': 'django-general'},
    'fastapi': {'bucket': 'framework/fastapi', 'globs': '**/*.py', 'base': 'fastapi-general'},
    'flask': {'bucket': 'framework/flask', 'globs': '**/*.py', 'base': 'flask-general'},
    'react': {'bucket': 'framework/react', 'globs': '**/*.{jsx,tsx,css,scss,html,vue}', 'base': 'react-general'},
    'react-native': {'bucket': 'framework/react', 'globs': '**/*.{jsx,tsx,css,scss,html,vue}', 'base': 'react-native-general'},
    'expo': {'bucket': 'framework/react', 'globs': '**/*.{jsx,tsx,css,scss,html,vue}', 'base': 'expo-general'},
    'vue': {'bucket': 'framework/vue', 'globs': '**/*.vue', 'base': 'vue-general'},
    'nuxt': {'bucket': 'framework/vue', 'globs': '**/*.vue', 'base': 'nuxt-general'},
    'node': {'bucket': 'platform/nodejs', 'globs': '**/*.{js,mjs,cjs,ts}', 'base': 'nodejs-general'},
    'nodejs': {'bucket': 'platform/nodejs', 'globs': '**/*.{js,mjs,cjs,ts}', 'base': 'nodejs-general'},
    'typescript': {'bucket': 'language/typescript', 'globs': '**/*.ts', 'base': 'typescript-general'},
    'javascript': {'bucket': 'language/javascript', 'globs': '**/*.{js,mjs,cjs}', 'base': 'javascript-general'},
    'chrome': {'bucket': 'platform/chrome', 'globs': '**/*.{js,ts,json}', 'base': 'chrome-extension-general'},
    'extension': {'bucket': 'platform/chrome', 'globs': '**/*.{js,ts,json}', 'base': 'chrome-extension-general'},
    'php': {'bucket': 'language/php', 'globs': '**/*.php', 'base': 'php-general'},
    'laravel': {'bucket': 'framework/laravel', 'globs': '**/*.php', 'base': 'laravel-general'},
    'wordpress': {'bucket': 'framework/wordpress', 'globs': '**/*.php', 'base': 'wordpress-general'},
    'golang': {'bucket': 'language/golang', 'globs': '**/*.go', 'base': 'golang-general'},
    'rust': {'bucket': 'language/rust', 'globs': '**/*.rs', 'base': 'rust-general'},
    'testing': {'bucket': 'domain/testing', 'globs': '**/*.{spec,test}.{js,ts,tsx,py}', 'base': 'testing-general'},
    'serverless': {'bucket': 'domain/devops/serverless', 'globs': '**/*', 'base': 'serverless-general'},
    'devops': {'bucket': 'domain/devops/tooling', 'globs': '**/*', 'base': 'devops-general'},
    'general': {'bucket': 'general', 'globs': '**/*', 'base': 'general'},
}

def detect_technology(content: str) -> str:
    """Detect the primary technology from content."""
    content_lower = content.lower()

    # Priority order for technology detection
    priority_techs = [
        'chrome extension', 'chrome', 'extension',
        'react native', 'react-native', 'expo',
        'django', 'fastapi', 'flask',
        'typescript', 'javascript', 'node', 'nodejs',
        'python', 'php', 'laravel', 'wordpress',
        'vue', 'nuxt', 'golang', 'rust',
        'testing', 'serverless', 'devops'
    ]

    # Check for priority technologies first
    for tech in priority_techs:
        if tech in content_lower:
            # Handle special cases
            if tech in ['chrome extension', 'chrome', 'extension']:
                return 'chrome'
            elif tech in ['react native', 'react-native']:
                return 'react-native'
            elif tech == 'node':
                return 'nodejs'
            else:
                return tech

    return 'general'

def derive_title_and_description(content: str) -> Tuple[str, str]:
    """Derive title and description from content."""
    lines = content.strip().split('\n')
    first_line = lines[0].strip()

    # Try to extract meaningful title
    if first_line.startswith('You are an expert'):
        # Extract technology from expert statement
        tech_match = re.search(r'You are an expert in ([^.]*)', first_line, re.IGNORECASE)
        if tech_match:
            tech = tech_match.group(1).strip()
            title = f"{tech} Expert Rules"
        else:
            title = "Expert Development Rules"
    elif first_line.startswith('#'):
        title = first_line.lstrip('#').strip()
    else:
        # Use first few words as title
        words = first_line.split()[:5]
        title = ' '.join(words).strip()
        if not title:
            title = "General Rules"

    # Clean up title
    title = re.sub(r'[^\w\s-]', '', title)
    title = re.sub(r'\s+', ' ', title)

    # Create description
    description = f"Guidelines and best practices for {title.lower()}"

    return title, description

def create_kebab_case_filename(title: str, tech: str) -> str:
    """Create kebab-case filename."""
    # Remove special characters and convert to lowercase
    clean_title = re.sub(r'[^\w\s]', '', title.lower())
    # Replace spaces with hyphens
    kebab = re.sub(r'\s+', '-', clean_title.strip())
    return f"{kebab}-{tech}.mdc"

def create_frontmatter(title: str, description: str, globs: str) -> str:
    """Create YAML frontmatter."""
    return f"""---
description: "{description}"
globs: "{globs}"
alwaysApply: false
---

# {title}

"""

def split_mdc_file(source_file: str, output_dir: str = "/workspace/frameworks/fwk-001-cursor-rules/DOCS/split/"):
    """Split the large MDC file into individual files."""
    source_path = Path(source_file)
    output_path = Path(output_dir)

    # Create output directories
    output_path.mkdir(parents=True, exist_ok=True)
    rules_path = Path("/workspace/.cursor/rules")
    rules_path.mkdir(parents=True, exist_ok=True)

    # Read the entire file
    with open(source_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by various separators
    separators = [
        r'\n---\n',  # Triple dash separator
        r'\nYou are an expert',  # New expert section
        r'\n# Rules for',  # Rules section
    ]

    sections = []
    current_content = content

    # First, split by "---" separators
    parts = re.split(r'\n---\n', content)
    if len(parts) > 1:
        for part in parts:
            if part.strip():
                sections.append(part.strip())
    else:
        # If no "---" separators, try other patterns
        current_content = content
        while current_content:
            # Find the next "You are an expert" line
            match = re.search(r'\nYou are an expert', current_content)
            if match:
                # Extract content before this match
                before = current_content[:match.start()].strip()
                if before:
                    sections.append(before)

                # Continue with the rest
                current_content = current_content[match.start():]
            else:
                # No more matches, add remaining content
                if current_content.strip():
                    sections.append(current_content.strip())
                break

    # Process each section
    processed_files = []

    for i, section in enumerate(sections):
        if not section.strip() or len(section.strip()) < 10:
            continue

        # Detect technology
        tech = detect_technology(section)

        # Get mapping for this technology
        mapping = MAPPING.get(tech, MAPPING['general'])

        # Derive title and description
        title, description = derive_title_and_description(section)

        # Create filename
        filename = create_kebab_case_filename(title, tech)

        # Create frontmatter
        frontmatter = create_frontmatter(title, description, mapping['globs'])

        # Combine content
        full_content = frontmatter + section

        # Write to split directory
        split_file = output_path / filename
        with open(split_file, 'w', encoding='utf-8') as f:
            f.write(full_content)

        # Also write to rules directory
        rules_subdir = rules_path / mapping['bucket']
        rules_subdir.mkdir(parents=True, exist_ok=True)
        rules_file = rules_subdir / filename
        with open(rules_file, 'w', encoding='utf-8') as f:
            f.write(full_content)

        processed_files.append({
            'title': title,
            'bucket': mapping['bucket'],
            'globs': mapping['globs'],
            'split_path': str(split_file),
            'rules_path': str(rules_file),
            'tech': tech
        })

    return processed_files

def generate_summary_report(processed_files: List[Dict]) -> str:
    """Generate a summary report."""
    report = "# MDC File Splitting Summary Report\n\n"
    report += f"Total files processed: {len(processed_files)}\n\n"
    report += "| Title | Bucket | Globs | Split Path | Rules Path |\n"
    report += "|-------|--------|-------|------------|------------|\n"

    for file_info in processed_files:
        report += f"| {file_info['title']} | {file_info['bucket']} | {file_info['globs']} | {file_info['split_path']} | {file_info['rules_path']} |\n"

    return report

def main():
    """Main function."""
    source_file = "/workspace/tools/asd.mdc"

    if not Path(source_file).exists():
        print(f"Error: Source file {source_file} does not exist.")
        return

    print(f"Processing {source_file}...")

    # Split the file
    processed_files = split_mdc_file(source_file)

    print(f"Successfully processed {len(processed_files)} sections.")

    # Generate and print summary
    summary = generate_summary_report(processed_files)
    print("\n" + "="*80)
    print(summary)
    print("="*80)

    # Save summary to file
    summary_file = "/workspace/frameworks/fwk-001-cursor-rules/DOCS/split/summary.md"
    Path(summary_file).parent.mkdir(parents=True, exist_ok=True)
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(summary)

    print(f"Summary saved to: {summary_file}")

if __name__ == "__main__":
    main()