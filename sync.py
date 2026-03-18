import requests
import json
import os
import time
from googletrans import Translator
from dotenv import load_dotenv

load_dotenv()

# AniList GraphQL API Endpoint
ANILIST_URL = 'https://graphql.anilist.co'

# AniList GraphQL Query
QUERY = '''
query ($page: Int, $perPage: Int, $type: MediaType) {
  Page (page: $page, perPage: $perPage) {
    pageInfo {
      total
      currentPage
      lastPage
      hasNextPage
      perPage
    }
    media (type: $type, sort: UPDATED_AT_DESC) {
      id
      title {
        romaji
        english
        native
      }
      description
      type
      format
      status
      episodes
      chapters
      volumes
      coverImage {
        large
      }
      bannerImage
      genres
      averageScore
      updatedAt
      trailer {
        id
        site
      }
    }
  }
}
'''

def fetch_anilist_data(media_type='ANIME', page=1, per_page=10):
    variables = {
        'page': page,
        'perPage': per_page,
        'type': media_type
    }
    
    response = requests.post(ANILIST_URL, json={'query': QUERY, 'variables': variables})
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None

def translate_text(text, target_lang='tr'):
    if not text:
        return ""
    
    # Remove HTML tags if present (AniList descriptions often have them)
    import re
    clean_text = re.sub('<[^<]+?>', '', text)
    
    translator = Translator()
    try:
        # Using googletrans for free translation
        translation = translator.translate(clean_text, dest=target_lang)
        return translation.text
    except Exception as e:
        print(f"Translation error: {e}")
        return clean_text # Fallback to original text

def process_media(media):
    # Process description: clean and translate
    original_description = media.get('description', '')
    translated_description = translate_text(original_description)
    
    # Format links for images/videos
    # AniList already provides links, we just need to ensure they're handled as links
    # Cover image: media['coverImage']['large']
    # Banner: media['bannerImage']
    # Trailer: if media['trailer'] and media['trailer']['site'] == 'youtube', link is https://www.youtube.com/watch?v={media['trailer']['id']}
    
    processed_data = {
        'id': media['id'],
        'title_romaji': media['title']['romaji'],
        'title_english': media['title']['english'],
        'title_native': media['title']['native'],
        'description_tr': translated_description,
        'description_en': original_description,
        'type': media['type'],
        'format': media['format'],
        'status': media['status'],
        'episodes': media.get('episodes'),
        'chapters': media.get('chapters'),
        'volumes': media.get('volumes'),
        'cover_image': media['coverImage']['large'],
        'banner_image': media.get('bannerImage'),
        'genres': media['genres'],
        'average_score': media['averageScore'],
        'updated_at': media['updatedAt'],
        'trailer_link': f"https://www.youtube.com/watch?v={media['trailer']['id']}" if media.get('trailer') and media['trailer']['site'] == 'youtube' else None
    }
    
    return processed_data

def save_to_github(data, filename, media_type):
    # Ensure data directory exists
    os.makedirs('data', exist_ok=True)
    
    # Save individual file
    filepath = os.path.join('data', filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved: {filepath}")
    
    # Update central index.json
    index_path = os.path.join('data', 'index.json')
    index_data = []
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            try:
                index_data = json.load(f)
            except json.JSONDecodeError:
                index_data = []
    
    # Check if entry already exists in index
    existing_index = -1
    for i, item in enumerate(index_data):
        if item['id'] == data['id']:
            existing_index = i
            break
    
    # Create index entry (simplified metadata for the list)
    index_entry = {
        'id': data['id'],
        'title': data['title_english'] or data['title_romaji'],
        'type': data['type'],
        'format': data['format'],
        'cover_image': data['cover_image'],
        'updated_at': data['updated_at'],
        'filename': filename
    }
    
    if existing_index != -1:
        index_data[existing_index] = index_entry
    else:
        index_data.append(index_entry)
    
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

def main():
    # Fetch recent Anime
    print("Fetching recent anime...")
    anime_data = fetch_anilist_data(media_type='ANIME', per_page=10)
    if anime_data:
        for media in anime_data['data']['Page']['media']:
            filename = f"anime_{media['id']}.json"
            filepath = os.path.join('data', filename)
            
            # Check if we need an update
            needs_update = True
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    old_data = json.load(f)
                    if old_data.get('updated_at') == media['updatedAt']:
                        print(f"Skipping {media['id']} (no update needed)")
                        needs_update = False
            
            if needs_update:
                processed = process_media(media)
                save_to_github(processed, filename, 'ANIME')
                time.sleep(2) # Avoid translation rate limits

    # Fetch recent Manga
    print("Fetching recent manga...")
    manga_data = fetch_anilist_data(media_type='MANGA', per_page=10)
    if manga_data:
        for media in manga_data['data']['Page']['media']:
            filename = f"manga_{media['id']}.json"
            filepath = os.path.join('data', filename)
            
            # Check if we need an update
            needs_update = True
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    old_data = json.load(f)
                    if old_data.get('updated_at') == media['updatedAt']:
                        print(f"Skipping {media['id']} (no update needed)")
                        needs_update = False
            
            if needs_update:
                processed = process_media(media)
                save_to_github(processed, filename, 'MANGA')
                time.sleep(2) # Avoid translation rate limits

if __name__ == '__main__':
    main()
