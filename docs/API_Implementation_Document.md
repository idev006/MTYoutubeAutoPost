# MTYoutubeAutoPost - API Implementation Document

## Overview
MTYoutubeAutoPost is a private Windows desktop application for bulk uploading product marketing videos to YouTube.

## Purpose
- Upload product demonstration videos for e-commerce/affiliate marketing
- Organize videos into playlists by product category
- Generate consistent titles and descriptions with affiliate links

## YouTube API Usage

### Authentication
- OAuth 2.0 authentication flow
- User authenticates via Google consent screen
- Tokens stored locally on user's machine
- Scopes used:
  - youtube.upload
  - youtube.force-ssl
  - youtube

### API Endpoints Used

#### 1. videos.insert (Upload)
- **Purpose**: Upload new videos to user's channel
- **Method**: Resumable upload (chunks)
- **Data sent**: Video file, title, description, tags, category
- **Quota cost**: ~1,600 units per video

#### 2. videos.update
- **Purpose**: Update metadata of existing videos
- **Data updated**: Title, description, tags
- **Quota cost**: ~50 units

#### 3. channels.list
- **Purpose**: Get user's channel information
- **Quota cost**: ~1 unit

#### 4. playlists.list
- **Purpose**: List user's playlists
- **Quota cost**: ~1 unit

#### 5. playlists.insert
- **Purpose**: Create new playlist
- **Quota cost**: ~50 units

#### 6. playlistItems.insert
- **Purpose**: Add video to playlist
- **Quota cost**: ~50 units

## Data Storage
- Video IDs stored in local SQLite database
- Purpose: Duplicate detection (avoid re-uploading)
- Location: User's local machine only
- No cloud storage, no third-party sharing

## User Flow
1. User launches desktop application
2. User clicks "Authenticate" → OAuth consent screen
3. User selects folders containing videos + product JSON
4. Application reads product info and generates metadata
5. Application uploads videos via resumable upload
6. Videos are organized into playlists

## Security
- OAuth tokens stored locally
- No data transmitted to third parties
- User can revoke access anytime via Google Account

## Screenshots

[Main Window]
- Folder selection panel
- Upload progress display
- Task queue table
- Log output

[Authentication]
- OAuth button
- Status indicator

## Contact
Developer: JIRATTORN JITSIRI
Email: masteriii.dev1@gmail.com
