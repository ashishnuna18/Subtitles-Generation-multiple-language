#!/usr/bin/env python3

from tamil.txt2unicode import unicode2tab
import subprocess
import sys
import tempfile
import os

def overlay_tamil(video_path, subtitle_path, output_path, pr_color = "white", se_color = "black"):
    color_dict = {'yellow': '&HF00d5ff&',
              'black': '&HFF0000&',
              'white': '&H00FFFFFF&',
              'red': '&H000000FF&'}
    try:
    	srt_file = open(subtitle_path,'r')
    	try:
    	    unicode_text = ''.join(srt_file.readlines())
    	except:
    	    print(f"Unable to read file content")
    	finally:
    	    srt_file.close()
    except:
    	print(f"Input subtitle file not found at {subtitle_path}")
   
    
    tab_text = unicode2tab(unicode_text)

    TAB_SRT = 'tempSRT.srt'
    try:
    	f = open(f"{TAB_SRT}", "w")
    	try:
    	    f.write(tab_text)
    	except:
    	    print(f"Unable to write to file created at {TAB_SRT}")
    	finally:
    	    f.close()
    except:
    	print(f"Unable to create a temp file to dump TAB encoded output, please make sure file path {output_path} is not restricted access")
    
    
    pr_color_hex = color_dict[pr_color]
    se_color_hex = color_dict[se_color]
    ffmpeg_command = f"ffmpeg -i {video_path} -vf \"subtitles=./{TAB_SRT}:force_style='FontName=TAB-ELCOT-Trichy,PrimaryColour={pr_color_hex},SecondaryColour={se_color_hex}'\" {output_path}"

    try:
        subprocess.run(ffmpeg_command, shell = True)
    except:
        print("Error related to ffmpeg, please view ffmpeg output")

    try:
        os.remove(TAB_SRT)
    except:
        print("Unable to delete temporarily created file at {TAB_SRT}")

def main():

    video_path = sys.argv[1]
    subtitle_path = sys.argv[2]
    output_path = sys.argv[3]

    pr_color = sys.argv[4]
    if pr_color == "default":
        overlay_tamil(video_path, subtitle_path, output_path)
    else:
        se_color = sys.argv[5]
        overlay_tamil(video_path, subtitle_path, output_path, pr_color, se_color)

if __name__ =='__main__':
    main()
