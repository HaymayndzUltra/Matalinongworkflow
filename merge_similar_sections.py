#!/usr/bin/env python3
import re
from typing import List, Tuple, Dict

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

def get_technology_keywords(title: str) -> List[str]:
    """Extract technology keywords from section title."""
    # Common technology keywords
    tech_keywords = [
        'typescript', 'javascript', 'react', 'next.js', 'vue', 'nuxt', 'svelte', 'angular',
        'node.js', 'python', 'django', 'fastapi', 'flask', 'solidity', 'expo', 'react native',
        'tailwind', 'shadcn', 'radix', 'pixi.js', 'chrome extension', 'mobile', 'web',
        'api', 'rest', 'graphql', 'mongodb', 'postgresql', 'supabase', 'payload cms'
    ]
    
    title_lower = title.lower()
    found_keywords = []
    
    for keyword in tech_keywords:
        if keyword in title_lower:
            found_keywords.append(keyword)
    
    return found_keywords

def find_similar_sections(sections: List[Tuple[str, str, int, int]]) -> List[List[int]]:
    """Find sections with similar technology focus."""
    similar_groups = []
    processed = set()
    
    for i, (title1, content1, start1, end1) in enumerate(sections):
        if i in processed:
            continue
            
        group = [i]
        keywords1 = get_technology_keywords(title1)
        
        for j, (title2, content2, start2, end2) in enumerate(sections[i+1:], i+1):
            if j in processed:
                continue
                
            keywords2 = get_technology_keywords(title2)
            
            # Check if sections share significant technology overlap
            common_keywords = set(keywords1) & set(keywords2)
            if len(common_keywords) >= 2:  # At least 2 common technologies
                group.append(j)
                processed.add(j)
        
        if len(group) > 1:  # More than one section in group
            similar_groups.append(group)
            processed.add(i)
    
    return similar_groups

def merge_sections(content: str, sections: List[Tuple[str, str, int, int]], similar_groups: List[List[int]]) -> str:
    """Merge similar sections into one comprehensive section."""
    lines = content.split('\n')
    
    # Sort groups by line number (descending) to avoid index shifting
    for group in similar_groups:
        group.sort(reverse=True)
    
    # Process each group
    for group in similar_groups:
        if len(group) < 2:
            continue
            
        # Keep the first section, remove others
        keep_index = group[-1]  # First occurrence
        remove_indices = group[:-1]  # Remove duplicates
        
        print(f"Keeping section at line {sections[keep_index][2]}, removing {len(remove_indices)} duplicates")
        
        # Remove duplicate sections
        for remove_idx in remove_indices:
            start_line = sections[remove_idx][2]
            end_line = sections[remove_idx][3]
            
            if start_line <= end_line and start_line < len(lines) and end_line < len(lines):
                del lines[start_line:end_line + 1]
    
    return '\n'.join(lines)

def main():
    # Read kernel.md
    try:
        with open('kernel.md', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("Error: kernel.md not found in current directory")
        return
    
    print("Analyzing kernel.md for similar sections...")
    
    # Extract sections
    sections = extract_sections(content)
    print(f"Found {len(sections)} sections")
    
    # Find similar sections
    similar_groups = find_similar_sections(sections)
    
    if not similar_groups:
        print("No similar sections found!")
        return
    
    print(f"\nFound {len(similar_groups)} groups of similar sections:")
    for i, group in enumerate(similar_groups):
        print(f"  Group {i+1}: {len(group)} sections")
        for idx in group:
            title = sections[idx][0][:80] + "..." if len(sections[idx][0]) > 80 else sections[idx][0]
            print(f"    - {title}")
    
    # Ask user if they want to merge
    response = input("\nDo you want to merge similar sections? (y/N): ").strip().lower()
    
    if response in ['y', 'yes']:
        # Create backup
        with open('kernel.md.backup3', 'w', encoding='utf-8') as f:
            f.write(content)
        print("Created backup: kernel.md.backup3")
        
        # Merge sections
        merged_content = merge_sections(content, sections, similar_groups)
        
        # Write merged content
        with open('kernel.md', 'w', encoding='utf-8') as f:
            f.write(merged_content)
        
        print("Similar sections merged! kernel.md has been updated.")
        
        # Show file size comparison
        original_size = len(content)
        new_size = len(merged_content)
        print(f"Original size: {original_size:,} characters")
        print(f"New size: {new_size:,} characters")
        print(f"Removed: {original_size - new_size:,} characters")
    else:
        print("No changes made.")

if __name__ == "__main__":
    main()
