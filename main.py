#!/usr/bin/env python3
"""
TextGrid to ASS Converter for Karaoke

This script converts a TextGrid file from Montreal Forced Aligner to an ASS subtitle file for Aegisub,
specifically formatted for karaoke videos with phrases that last approximately 5 seconds each.

Usage:
    python textgrid_to_ass.py input.TextGrid output.ass [--tier TIER] [--style STYLE] [--phrase-marker MARKER] [--target-duration SECONDS]

Arguments:
    input.TextGrid    : Path to the input TextGrid file
    output.ass        : Path to the output ASS subtitle file
    --tier            : The tier name to extract (default: "words")
    --style           : The style name to use in the ASS file (default: "Default")
    --phrase-marker   : Marker that indicates phrase boundaries (default: "<eps>")
    --target-duration : Target duration for each subtitle line in seconds (default: 5.0)
"""

import re
import argparse
import datetime
from typing import List, Tuple, Dict, Any

def parse_textgrid(file_path: str) -> Dict[str, List[Tuple[float, float, str]]]:
    """
    Parse a TextGrid file and extract intervals from all tiers.
    
    Args:
        file_path: Path to the TextGrid file
        
    Returns:
        Dictionary with tier names as keys and lists of intervals (start_time, end_time, text) as values
    """
    with open(file_path, 'r', encoding='utf-16-be') as f:
        content = f.read()
    
    # Extract tier names
    tier_names = re.findall(r'name = "(.*?)"', content)
    
    # Initialize result dictionary
    tiers = {name: [] for name in tier_names}
    
    # Find all item (tier) blocks
    item_blocks = re.findall(r'item \[\d+\]:(.*?)(?=item \[\d+\]:|$)', content, re.DOTALL)
    
    for i, block in enumerate(item_blocks):
        if i >= len(tier_names):
            break
            
        tier_name = tier_names[i]
        
        # Extract all intervals
        intervals = re.findall(r'intervals \[\d+\]:\s+xmin = ([\d\.]+)\s+xmax = ([\d\.]+)\s+text = "(.*?)"', 
                              block, re.DOTALL)
        
        # Convert to list of tuples (start_time, end_time, text)
        intervals_list = [(float(start), float(end), text.strip()) for start, end, text in intervals]
        
        tiers[tier_name] = intervals_list
    
    return tiers

def format_time(seconds: float) -> str:
    """
    Convert seconds to ASS time format (h:mm:ss.cc)
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Time in ASS format (h:mm:ss.cc)
    """
    hours = int(seconds / 3600)
    minutes = int((seconds % 3600) / 60)
    seconds = seconds % 60
    centiseconds = int((seconds - int(seconds)) * 100)
    
    return f"{hours}:{minutes:02d}:{int(seconds):02d}.{centiseconds:02d}"

def group_into_phrases(intervals: List[Tuple[float, float, str]], phrase_marker: str = "<eps>", min_phrase_gap: float = 2.0, target_duration: float = 5.0) -> List[Tuple[float, float, List[Tuple[float, float, str, bool]]]]:
    """
    Group words into phrases based on phrase markers and timing constraints.
    Words with phrase markers will only create new phrases if they're more than min_phrase_gap seconds apart.
    
    Args:
        intervals: List of tuples (start_time, end_time, text)
        phrase_marker: Marker that indicates potential phrase boundaries
        min_phrase_gap: Minimum time gap (in seconds) between phrases
        target_duration: Target maximum duration for a phrase
        
    Returns:
        List of tuples (start_time, end_time, word_list) where word_list contains (start, end, text, has_marker)
    """
    phrases = []
    current_words = []
    current_start = None
    current_end = None
    last_phrase_end = 0
    
    filtered_intervals = []
    for start, end, text in intervals:
        # Skip empty intervals
        if not text.strip() or text == "<p:>":
            continue
            
        # Check if this text has a phrase marker
        has_marker = phrase_marker in text
        
        # Clean text by removing phrase markers
        # clean_text = text.replace(phrase_marker, "").strip()
        # if clean_text:  # Only keep intervals with text
        #     filtered_intervals.append((start, end, clean_text, has_marker))
        filtered_intervals.append((start, end, text, has_marker))

    for start, end, text, has_marker in filtered_intervals:
        # Initialize the first phrase
        if current_start is None:
            current_start = start
            
        # Start a new phrase if:
        # 1. This word contains a phrase marker AND
        # 2. It's been at least min_phrase_gap seconds since the last phrase ended AND
        # 3. We have some words accumulated
        phrase_marker_condition = (has_marker and start - last_phrase_end >= min_phrase_gap and current_words)
        
        # Or if the current phrase is getting too long
        duration_condition = (end - current_start > target_duration and current_words)
        
        if phrase_marker_condition or duration_condition:
            # Complete current phrase
            if current_words:
                # Add phrase marker to the last word of the current phrase if it exists
                if has_marker:
                    last_word = current_words[-1]
                    current_words[-1] = (last_word[0], last_word[1], last_word[2], last_word[3])
                phrases.append((current_start, current_end, current_words))
                last_phrase_end = current_end
            
            # Start a new phrase
            current_words = [(start, end, text.replace(phrase_marker, " ").strip(), has_marker)]
            current_start = start
            current_end = end
        else:
            # Add to current phrase
            current_words.append((start, end, text.replace(phrase_marker, " ").strip(), has_marker))
            current_end = end
    
    # Add the last phrase if there's anything left
    if current_words and current_start is not None:
        phrases.append((current_start, current_end, current_words))
    
    return phrases

def create_karaoke_line(words: List[Tuple[float, float, str, bool]]) -> str:
    """
    Create a karaoke line with timing tags for each word.
    When a word had a phrase marker in the original text, insert a visual space before it.
    
    Args:
        words: List of (start_time, end_time, text, has_marker) tuples representing words in a phrase
        
    Returns:
        String with karaoke timing tags for ASS format
    """
    result = ""
    
    for i, (start, end, text, has_marker) in enumerate(words):
        # Calculate duration of this word in centiseconds
        duration_cs = int((end - start) * 100)
        
        # Insert space before words that had a phrase marker (except for the first word)
        if i > 0 and has_marker:
            result += " "
        
        # Add karaoke tag with duration
        # engilsh needs a space and chinese doesn't
        result += f"{{\\K{duration_cs}}}{text} "
        
        #Chinese
        #result += f"{{\\K{duration_cs}}}{text}""
    
    return result

def create_ass_file(intervals: List[Tuple[float, float, str]], output_file: str, style_name: str = "Default", 
                   phrase_marker: str = "<eps>", min_phrase_gap: float = 2.0, target_duration: float = 5.0, shift_time: float = 0.0):
    """
    Create an ASS subtitle file with karaoke timing tags.
    
    Args:
        intervals: List of tuples (start_time, end_time, text)
        output_file: Path to the output ASS file
        style_name: Style name to use in the ASS file
        phrase_marker: Marker that indicates phrase boundaries
        min_phrase_gap: Minimum time gap (in seconds) between phrases
        target_duration: Target maximum duration for a phrase
    """
    # ASS header for karaoke
    header = f"""[Script Info]
; Script generated by TextGrid to ASS Converter for Karaoke
Title: Karaoke from TextGrid
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: {style_name},Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,2,2,2,10,10,40,1
Style: Voice1,Microsoft PhagsPa,80,&H00D58847,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,1,100,10,100,1
Style: Voice2,Microsoft PhagsPa,80,&H0092D8F9,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,3,10,100,10,1
Style: Line1,Microsoft PhagsPa,100,&H00FFDB00,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,1,100,10,170,1
Style: Line2,Microsoft PhagsPa,100,&H00FFDB00,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,3,0,100,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    # Group intervals into phrases
    phrases = group_into_phrases(intervals, phrase_marker, min_phrase_gap, target_duration)
    
    # Create karaoke events
    events = []
    for i, (start, end, words) in enumerate(phrases, 1):

        # Shift start time if specified
        shifted_start = max(0, start + shift_time)

        start_time = format_time(shifted_start)
        end_time = format_time(end)
        
        # Create karaoke line with timing tags
        karaoke_text = create_karaoke_line(words)
        
        # Shift effect tag to start with consideration to time shift
        karaoke_text = f"{{\\K{int(shift_time * -100)}}}{karaoke_text}"
        
        # Add dialogue line
        events.append(f"Dialogue: 0,{start_time},{end_time},{style_name},,0,0,0,,{karaoke_text}")
    
    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(header)
        f.write("\n".join(events))

def main():
    parser = argparse.ArgumentParser(description='Convert TextGrid file to ASS subtitle file for karaoke')
    parser.add_argument('input', help='Input TextGrid file')
    parser.add_argument('output', help='Output ASS file')
    parser.add_argument('--tier', default='words', help='TextGrid tier to extract (default: "words")')
    parser.add_argument('--style', default='Default', help='Style name in ASS file (default: "Default")')
    parser.add_argument('--phrase-marker', default='<eps>', help='Marker that indicates phrase boundaries (default: "<eps>")')
    parser.add_argument('--min-phrase-gap', type=float, default=2.0, 
                        help='Minimum time gap (in seconds) between phrases (default: 2.0)')
    parser.add_argument('--target-duration', type=float, default=5.0, 
                        help='Target maximum duration for a phrase (default: 5.0)')
    parser.add_argument('--shift-time', type=float, help='Time to shift the start of phrases (default: 0.0). Use negative float only. Negative number means showing the subtitle earlier - <----------- 0 -----------> +')
    
    args = parser.parse_args()
    
    # Parse TextGrid file
    tiers = parse_textgrid(args.input)
    
    # Check if specified tier exists
    if args.tier not in tiers:
        available_tiers = ", ".join(f'"{tier}"' for tier in tiers.keys())
        print(f'Tier "{args.tier}" not found. Available tiers: {available_tiers}')
        return
    
    # Create ASS file with karaoke formatting
    create_ass_file(
        tiers[args.tier], 
        args.output, 
        args.style, 
        args.phrase_marker, 
        args.min_phrase_gap,
        args.target_duration,
        args.shift_time
    )
    print(f'Successfully converted "{args.input}" to "{args.output}" using tier "{args.tier}"')
    print(f'Phrases are grouped with "{args.phrase_marker}" markers with a minimum gap of {args.min_phrase_gap}s')
    print(f'Target maximum phrase duration: {args.target_duration}s')
    print(f'Karaoke timing tags (\\K) have been added for each word')

if __name__ == "__main__":
    main()
