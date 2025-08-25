#!/usr/bin/env python3
import re
import hashlib
from typing import List, Tuple

def extract_sections(content: str) -> List[Tuple[str, str, int, int]]:
    """Extract sections starting with 'You are an expert' and their content."""
    sections = []
    lines = content.split('\n')
    current_section = []
    current_title = ""
    start_line = 0
    
    for i, line in enumerate(lines):
        if line.strip().startswith("You are an expert"):
            # Save previous section if exists
            if current_title and current_section:
                sections.append((current_title, '\n'.join(current_section), start_line, i-1))
            
            # Start new section
            current_title = line.strip()
            current_section = [line]
            start_line = i
        elif current_title:
            current_section.append(line)
    
    # Add last section
    if current_title and current_section:
        sections.append((current_title, '\n'.join(current_section), start_line, len(lines)-1))
    
    return sections

def find_exact_duplicates(sections: List[Tuple[str, str, int, int]]) -> List[Tuple[int, int, int, int]]:
    """Find only exact duplicate sections."""
    duplicates = []
    
    for i, (title1, content1, start1, end1) in enumerate(sections):
        for j, (title2, content2, start2, end2) in enumerate(sections[i+1:], i+1):
            # Only consider exact matches
            if content1.strip() == content2.strip():
                duplicates.append((start1, end1, start2, end2))
    
    return duplicates

def remove_exact_duplicates(content: str, duplicates: List[Tuple[int, int, int, int]]) -> str:
    """Remove only exact duplicate sections."""
    lines = content.split('\n')
    
    # Sort duplicates by line number (descending) to avoid index shifting
    duplicates.sort(key=lambda x: x[1], reverse=True)
    
    removed_count = 0
    for start1, end1, start2, end2 in duplicates:
        # Remove the second occurrence (keep the first one)
        if start2 <= end2 and start2 < len(lines) and end2 < len(lines):
            del lines[start2:end2 + 1]
            removed_count += 1
    
    print(f"Removed {removed_count} exact duplicate sections")
    return '\n'.join(lines)

def main():
    # Read kernel.md
    try:
        with open('kernel.md', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("Error: kernel.md not found in current directory")
        return
    
    print("Analyzing kernel.md for EXACT duplicates only...")
    
    # Extract sections
    sections = extract_sections(content)
    print(f"Found {len(sections)} sections")
    
    # Find exact duplicates only
    duplicates = find_exact_duplicates(sections)
    
    if not duplicates:
        print("No exact duplicates found!")
        return
    
    print(f"\nFound {len(duplicates)} EXACT duplicate sections:")
    for start1, end1, start2, end2 in duplicates:
        print(f"  Lines {start1}-{end1} and {start2}-{end2} are identical")
    
    # Ask user if they want to remove duplicates
    response = input("\nDo you want to remove EXACT duplicates only? (y/N): ").strip().lower()
    
    if response in ['y', 'yes']:
        # Create backup
        with open('kernel.md.backup2', 'w', encoding='utf-8') as f:
            f.write(content)
        print("Created backup: kernel.md.backup2")
        
        # Remove exact duplicates only
        cleaned_content = remove_exact_duplicates(content, duplicates)
        
        # Write cleaned content
        with open('kernel.md', 'w', encoding='utf-8') as f:
            f.write(cleaned_content)
        
        print("Exact duplicates removed! kernel.md has been updated.")
        
        # Show file size comparison
        original_size = len(content)
        new_size = len(cleaned_content)
        print(f"Original size: {original_size:,} characters")
        print(f"New size: {new_size:,} characters")
        print(f"Removed: {original_size - new_size:,} characters")
    else:
        print("No changes made.")

if __name__ == "__main__":
    main()
