from moviepy.editor import *
import os
import difflib
import itertools
import whisper_timestamped as whisper
import shutil
import sys

#chunking helper functions
def chunk_video(input_video, chunk_duration=30):
    clip = VideoFileClip(input_video)
    total_duration = clip.duration
    chunks = []
    filename = os.path.basename(input_video)
    print(filename)
    start_time = 0
    idx = 0
    while start_time < total_duration:
        end_time = min(start_time + chunk_duration, total_duration)
        chunk = clip.subclip(start_time, end_time)
        chunks.append(chunk)
        start_time += chunk_duration
    for idx, chunk in enumerate(chunks):
      audio = chunk.audio
      if os.path.exists(f"{filename}_tmp"):
        audio.write_audiofile(f"./{filename}_tmp/chunk_{idx}.mp3")
      else:
        os.mkdir(f"./{filename}_tmp")
        audio.write_audiofile(f"./{filename}_tmp/chunk_{idx}.mp3")

def retrive_overlaps(input_video,chunk_duration = 30, overlap_buffer = 5):
  clip = VideoFileClip(input_video)
  total_duration = clip.duration
  overlaps = []
  filename = os.path.basename(input_video)
  start_time = chunk_duration - (overlap_buffer/2)
  idx = 0
  while start_time < total_duration:
    end_time = min(start_time + overlap_buffer,total_duration)
    chunk = clip.subclip(start_time, end_time)
    overlaps.append(chunk)
    start_time += chunk_duration

  for idx, overlap in enumerate(overlaps):
    audio = overlap.audio
    audio.write_audiofile(f"./{filename}_tmp/overlap_{idx}.mp3")

def retrieve_nonoverlap_ids(chunks_transcribed,overlaps_transcribed,confidence_threshold = 0.65):
  no_of_chunks = len(chunks_transcribed)
  indices = []
  for i in range(no_of_chunks):
    no_segments_chunk1 = len(chunks_transcribed[i]['segments'])

    chunk1_raw = []
    for segment in chunks_transcribed[i]['segments']:
      chunk1_raw.extend(segment['words'])
    chunk1_text = ' '.join([word['text'] for word in chunk1_raw if word['confidence'] > confidence_threshold])

    overlap_text = overlaps_transcribed[i]['text']
    words = []
    for segment in overlaps_transcribed[i]['segments']:
      segment_words = [word['text'] for word in segment['words']]
      words.extend(segment_words)

    print(words)


    if i == no_of_chunks-1:
      break

    chunk2_raw = []
    for segment in chunks_transcribed[i+1]['segments']:
      chunk2_raw.extend(segment['words'])
    chunk2_text = ' '.join([word['text'] for word in chunk2_raw if word['confidence'] > confidence_threshold])

    overlap_tokens = overlap_text.replace(',', '').replace('.', '').split()
    chunk1_tokens = chunk1_text.replace(',', '').replace('.', '').split()

    chunk2_tokens = chunk2_text.replace(',', '').replace('.', '').split()
    print(chunk1_tokens, chunk2_tokens, overlap_tokens)
   
    # Find common sentences between overlap and chunk1
    matcher = difflib.SequenceMatcher(None, overlap_tokens, chunk1_tokens)
    common_overlap_chunk1 = matcher.find_longest_match(0, len(overlap_tokens), 0, len(chunk1_tokens))

    # Find common sentences between overlap and chunk2
    matcher = difflib.SequenceMatcher(None, overlap_tokens, chunk2_tokens)
    common_overlap_chunk2 = matcher.find_longest_match(0, len(overlap_tokens), 0, len(chunk2_tokens))

    print(common_overlap_chunk1, common_overlap_chunk2)
    indices.append([common_overlap_chunk1[0]+common_overlap_chunk1[2], common_overlap_chunk2[0]])
  return indices

def chunk_transcribe(model_name,input_video,chunk_length, overlap_buffer,language = "none",vad = True, overlap = True, confidence_threshold = 0.65):
  model = whisper.load_model(model_name, device = "cuda")
  filename = os.path.basename(input_video) #name of input video
  if(os.path.exists('./{filename}_tmp') == False):
  #CHUNKING
    chunk_video(input_video, chunk_length)
  #CREATING OVERLAP CHUNKS B/W CHUNKS
  retrive_overlaps(input_video, chunk_length, overlap_buffer)


  #walking created chunks directory
  chunk_names = []
  for root, dirs, files in os.walk(f"{filename}_tmp"):
    for file in files:
      if file.startswith('chunk'):
        chunk_names.append(os.path.join(root, file))

  #TRANSCRIBING WITH WHISPER-TIMESTAMPPED
  chunks_transcribed = []
  overlaps_transcribed = []
  print(chunk_names)
  for idx in range(len(chunk_names)):
    #chunks
    chunk_audio = whisper.load_audio(f"{filename}_tmp/chunk_{idx}.mp3")
    #overlaps
    if idx != len(chunks_transcribed)-1:
        overlap_audio = whisper.load_audio(f"{filename}_tmp/overlap_{idx}.mp3")
    if language == "none":
      chunk_result = whisper.transcribe(model, chunk_audio,vad = vad)
      overlap_result = whisper.transcribe(model, overlap_audio, vad = vad)
    else:
      chunk_result = whisper.transcribe(model, chunk_audio, language = language, vad = vad)
      overlap_result = whisper.transcribe(model, overlap_audio,language = language, vad = vad)
    chunks_transcribed.append(chunk_result)
    overlaps_transcribed.append(overlap_result)

  #CREATING SRT
  global_id = 0
  srt = ""
  indices= retrieve_nonoverlap_ids(chunks_transcribed,overlaps_transcribed)
  print(indices)
  for idx in range(len(chunks_transcribed)):
    chunk_result = chunks_transcribed[idx]
    overlap_result = overlaps_transcribed[idx]

    #chunk
    no_chunk_segments = len(chunk_result['segments'])
    for i, segment in enumerate(chunk_result['segments']):
      #print(segment['text'])
      if i == 0 or i == no_chunk_segments-1:
        if segment['confidence'] < confidence_threshold:
          continue
        id = str(global_id) + "\n"
        words = [word for word in segment['words'] if word['confidence'] > confidence_threshold]
        text = ' '.join([word['text'] for word in words])
        if len(words) == 0:
          continue
        #print(words)
        start, end = words[0]['start'], words[-1]['end']

        if i == 0:
            start = (idx)*chunk_length + (overlap_buffer/4)
            print('FIRST CHUNK START TIME-', start)
            timestamp = f"00:00:{str(round(float(start),3)).replace('.', ',')} --> 00:00:{str(round(float(end)+idx*chunk_length,3)).replace('.', ',')}\n"

        else:
            end = (idx+1)*chunk_length - (overlap_buffer/4)
            timestamp = f"00:00:{str(round(float(start)+idx*chunk_length,3)).replace('.', ',')} --> 00:00:{str(round(float(end),3)).replace('.', ',')}\n"

        #timestamp = f"00:00:{str(round(float(start)+idx*chunk_length,3)).replace('.', ',')} --> 00:00:{str(round(float(end)+idx*chunk_length,3)).replace('.', ',')}\n"
        spacing = "\n\n"
        srt = srt + id + timestamp + text + spacing
        global_id += 1
        continue

      if segment['confidence'] < confidence_threshold:
          continue
      start, end = segment['start'], segment['end']
      id = str(global_id) + "\n"
      #timestamp = f"00:00:{str(round(float(start)+idx*chunk_length,3)).replace('.', ',')} --> 00:00:{str(round(float(end)+idx*chunk_length,3)).replace('.', ',')}\n"
      timestamp = f"00:00:{str(round(float(start)+idx*chunk_length,3)).replace('.', ',')} --> 00:00:{str(round(float(end)+idx*chunk_length,3)).replace('.', ',')}\n"
      text = segment['text'].strip()
      spacing = "\n\n"
      srt = srt + id + timestamp + text + spacing
      global_id += 1

    #overlap
    print("####",idx,"#####")
    if overlap == True:
      if idx < len(chunks_transcribed)-1:

        start_id, end_id = indices[idx][0]-1, indices[idx][1]-1

        words = []
        words_metadata = []

        for segment in overlaps_transcribed[idx]['segments']:
          segment_text = " ".join([word['text'] for word in segment['words']])
          words_metadata.extend(segment['words'])
          words.extend(segment_text)

        if len(words_metadata) == 0:
            continue
        if start_id <= 0:
          start_id = 0
        if end_id <= 0:
          end_id = len(words_metadata)-1
        if start_id == end_id:
          continue
        print(start_id, end_id)
        print(words_metadata)
        start = (idx+1)*chunk_length - (overlap_buffer/4)
        end = (idx+1)*chunk_length + (overlap_buffer/4)
        print(start,end)
        timestamp = f"00:00:{str(round(float(start),3)).replace('.', ',')} --> 00:00:{str(round(float(end),3)).replace('.', ',')}\n"

        id = str(global_id) + "\n"
        #text = ' '.join(words_metadata[start_id:end_id+1])
        text = ' '.join([word['text'] for word in words_metadata[start_id:end_id+1]])
        if text == "":
          continue

        print(text)
        spacing = "\n\n"
        srt = srt + id + timestamp + text + spacing
        #srt = srt[:-2]
        #srt = srt +" overlap- "+ text + spacing
        global_id += 1
    print(model_name)
    #model_name = model_name.split('/')
    with open(f'{filename}_{chunk_length}_{overlap_buffer}_{language}_{"VAD" if vad else "noVAD"}_{"Overlap" if overlap else "noOverlap"}_{confidence_threshold}_{model_name[1]}.srt', "w", encoding="utf-8") as file:
      file.write(srt)
    #del model

def load_whisper(id = "openai/whisper-large-v3", device = "cuda"):
  model = whisper.load_model(id, device = device)
  return model

###################################################################

###################################################################
def main():
#print("hello")
  input_video = sys.argv[1]
  print(input_video)
  #loading english model-
  #model = load_whisper("openai/whisper-large-v3", device = "cuda")
  #creating english srt file
  chunk_transcribe("openai/whisper-large-v3", input_video,30,5,language = "en", confidence_threshold = 0.90,overlap = True)

  #unloading and onloading tamil model
  #del model
  #model = load_whisper("kurianbenoy/whisper-medium-tamil", device = "cuda")
  #creating tamil srt file
  chunk_transcribe("openai/whisper-large-v3", input_video, 30, 5,language = "hi",confidence_threshold = 0.65,overlap = True)
  filename = os.path.basename(input_video)
  shutil.rmtree(f"{input_video}_tmp")

if __name__ == "__main__":
    main()
