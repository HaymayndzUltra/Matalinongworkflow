#!/usr/bin/env python3
import re
import hashlib
from typing import List, Dict, Tuple

def extract_sections(content: str) -> List[Tuple[str, str, int]]:
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
                sections.append((current_title, '\n'.join(current_section), start_line))
            
            # Start new section
            current_title = line.strip()
            current_section = [line]
            start_line = i + 1
        elif current_title:
            current_section.append(line)
    
    # Add last section
    if current_title and current_section:
        sections.append((current_title, '\n'.join(current_section), start_line))
    
    return sections

def find_duplicates(sections: List[Tuple[str, str, int]]) -> List[Tuple[int, int, float]]:
    """Find duplicate sections based on content similarity."""
    duplicates = []
    
    for i, (title1, content1, line1) in enumerate(sections):
        for j, (title2, content2, line2) in enumerate(sections[i+1:], i+1):
            # Calculate similarity
            similarity = calculate_similarity(content1, content2)
            if similarity > 0.8:  # 80% similarity threshold
                duplicates.append((line1, line2, similarity))
    
    return duplicates

def calculate_similarity(content1: str, content2: str) -> float:
    """Calculate similarity between two content strings."""
    # Normalize content
    norm1 = re.sub(r'\s+', ' ', content1.strip().lower())
    norm2 = re.sub(r'\s+', ' ', content2.strip().lower())
    
    # Use hash-based comparison for efficiency
    hash1 = hashlib.md5(norm1.encode()).hexdigest()
    hash2 = hashlib.md5(norm2.encode()).hexdigest()
    
    if hash1 == hash2:
        return 1.0
    
    # Simple word overlap similarity
    words1 = set(norm1.split())
    words2 = set(norm2.split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    return intersection / union if union > 0 else 0.0

def remove_duplicates(content: str, duplicates: List[Tuple[int, int, float]]) -> str:
    """Remove duplicate sections from content."""
    lines = content.split('\n')
    
    # Sort duplicates by line number (descending) to avoid index shifting
    duplicates.sort(key=lambda x: x[1], reverse=True)
    
    for _, duplicate_line, _ in duplicates:
        # Find the section boundaries
        section_start = duplicate_line - 1
        section_end = duplicate_line - 1
        
        # Find section start (previous "You are an expert" line)
        for i in range(section_start - 1, -1, -1):
            if i < len(lines) and lines[i].strip().startswith("You are an expert"):
                section_start = i
                break
        
        # Find section end (next "You are an expert" line or end of file)
        for i in range(section_end + 1, len(lines)):
            if i < len(lines) and lines[i].strip().startswith("You are an expert"):
                section_end = i - 1
                break
        else:
            section_end = len(lines) - 1
        
        # Ensure bounds are valid
        section_start = max(0, min(section_start, len(lines) - 1))
        section_end = max(0, min(section_end, len(lines) - 1))
        
        # Remove the duplicate section
        if section_start <= section_end:
            del lines[section_start:section_end + 1]
    
    return '\n'.join(lines)

def main():
    # Read kernel.md
    try:
        with open('kernel.md', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("Error: kernel.md not found in current directory")
        return
    
    print("Analyzing kernel.md for duplicates...")
    
    # Extract sections
    sections = extract_sections(content)
    print(f"Found {len(sections)} sections")
    
    # Find duplicates
    duplicates = find_duplicates(sections)
    
    if not duplicates:
        print("No duplicates found!")
        return
    
    print(f"\nFound {len(duplicates)} duplicate sections:")
    for line1, line2, similarity in duplicates:
        print(f"  Lines {line1} and {line2} - {similarity:.1%} similar")
    
    # Ask user if they want to remove duplicates
    response = input("\nDo you want to remove duplicates? (y/N): ").strip().lower()
    
    if response in ['y', 'yes']:
        # Create backup
        with open('kernel.md.backup', 'w', encoding='utf-8') as f:
            f.write(content)
        print("Created backup: kernel.md.backup")
        
        # Remove duplicates
        cleaned_content = remove_duplicates(content, duplicates)
        
        # Write cleaned content
        with open('kernel.md', 'w', encoding='utf-8') as f:
            f.write(cleaned_content)
        
        print("Duplicates removed! kernel.md has been updated.")
    else:
        print("No changes made.")

if __name__ == "__main__":
    main()
