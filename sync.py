import requests
import json
import os
import time
import re
import argparse
from googletrans import Translator
from dotenv import load_dotenv

load_dotenv()

# AniList GraphQL API Endpoint
ANILIST_URL = 'https://graphql.anilist.co'

# AniList GraphQL Queries
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

SEARCH_QUERY = '''
query ($search: String, $type: MediaType) {
  Page (page: 1, perPage: 5) {
    media (search: $search, type: $type) {
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
        return None

def search_anilist(search_term, media_type='ANIME'):
    variables = {
        'search': search_term,
        'type': media_type
    }
    response = requests.post(ANILIST_URL, json={'query': SEARCH_QUERY, 'variables': variables})
    if response.status_code == 200:
        return response.json()
    return None

def translate_text(text, target_lang='tr'):
    if not text:
        return ""
    clean_text = re.sub('<[^<]+?>', '', text)
    translator = Translator()
    try:
        translation = translator.translate(clean_text, dest=target_lang)
        return translation.text
    except Exception as e:
        print(f"Translation error: {e}")
        return clean_text

def process_media(media):
    # Title translation
    original_title = media['title']['english'] or media['title']['romaji']
    translated_title = translate_text(original_title)
    
    # Description translation
    original_description = media.get('description', '')
    translated_description = translate_text(original_description)
    
    processed_data = {
        'id': media['id'],
        'title_tr': translated_title,
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
    # Root level folders: anime/ or manga/
    sub_dir = media_type.lower()
    os.makedirs(sub_dir, exist_ok=True)
    
    # Save individual file in its folder
    filepath = os.path.join(sub_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Keep index.json in data/ for the web app
    os.makedirs('data', exist_ok=True)
    index_path = os.path.join('data', 'index.json')
    index_data = []
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            try:
                index_data = json.load(f)
            except:
                index_data = []
    
    existing_index = -1
    for i, item in enumerate(index_data):
        if item['id'] == data['id']:
            existing_index = i
            break
            
    index_entry = {
        'id': data['id'],
        'title_tr': data['title_tr'],
        'title_original': data['title_english'] or data['title_romaji'],
        'type': data['type'],
        'format': data['format'],
        'cover_image': data['cover_image'],
        'genres': data['genres'], # Added for archive searching
        'updated_at': data['updated_at'],
        'filename': f"../{sub_dir}/{filename}" 
    }
    
    if existing_index != -1:
        index_data[existing_index] = index_entry
    else:
        index_data.append(index_entry)
        
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    print(f"Saved: {data['id']} - {data['title_tr']}")

ID_QUERY = '''
query ($id: Int) {
  Media (id: $id) {
    id
    title { romaji english native }
    description
    type
    format
    status
    episodes
    chapters
    volumes
    coverImage { large }
    bannerImage
    genres
    averageScore
    updatedAt
    trailer { id site }
  }
}
'''

def get_anilist_by_id(media_id):
    variables = {'id': int(media_id)}
    response = requests.post(ANILIST_URL, json={'query': ID_QUERY, 'variables': variables})
    if response.status_code == 200:
        return response.json()
    return None

def main():
    parser = argparse.ArgumentParser(description='AniList Sync & Search Tool')
    parser.add_argument('--search', type=str, help='Search and add a specific title')
    parser.add_argument('--id', type=int, help='Add a specific title by ID')
    parser.add_argument('--type', type=str, default='ANIME', choices=['ANIME', 'MANGA'], help='Media type')
    parser.add_argument('--sync', action='store_true', help='Sync recent updates')
    
    args = parser.parse_args()

    if args.id:
        print(f"Fetching ID {args.id}...")
        results = get_anilist_by_id(args.id)
        if results and results.get('data', {}).get('Media'):
            media = results['data']['Media']
            print(f"Found: {media['title']['english'] or media['title']['romaji']}")
            processed = process_media(media)
            save_to_github(processed, f"{media['type'].lower()}_{media['id']}.json", media['type'])
        else:
            print(f"ID {args.id} not found.")
        return

    if args.search:
        print(f"Searching for '{args.search}'...")
        results = search_anilist(args.search, args.type)
        if results and results['data']['Page']['media']:
            for i, media in enumerate(results['data']['Page']['media']):
                print(f"[{i}] {media['title']['english'] or media['title']['romaji']} (ID: {media['id']})")
            
            # For simplicity in automation, we take the first one or we can prompt
            media = results['data']['Page']['media'][0]
            print(f"Processing: {media['title']['romaji']}...")
            processed = process_media(media)
            save_to_github(processed, f"{args.type.lower()}_{media['id']}.json", args.type)
        else:
            print("No results found.")
        return

    # Default: Sync recent updates
    for mtype in ['ANIME', 'MANGA']:
        print(f"Fetching recent {mtype}...")
        data = fetch_anilist_data(media_type=mtype, per_page=10)
        if data:
            for media in data['data']['Page']['media']:
                filename = f"{mtype.lower()}_{media['id']}.json"
                filepath = os.path.join('data', filename)
                
                needs_update = True
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        old_data = json.load(f)
                        if old_data.get('updated_at') == media['updatedAt']:
                            needs_update = False
                
                if needs_update:
                    processed = process_media(media)
                    save_to_github(processed, filename, mtype)
                    time.sleep(1)

if __name__ == '__main__':
    main()
