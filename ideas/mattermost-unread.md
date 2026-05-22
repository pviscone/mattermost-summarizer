Based on my research:

**Yes, the Mattermost API can expose unread messages using a personal access token.**

## Endpoint

```
GET /api/v4/users/{user_id}/channels/{channel_id}/unread
```

This returns a `ChannelUnread` object containing:
- `msg_count` / `msg_count_root` - number of read messages
- `mention_count` / `mention_count_root` - unread mentions
- `urgent_mention_count` - urgent mentions
- `deltaMsgs` - unread message count
- `last_viewed_at`

## Personal Access Token Compatibility

Yes, personal access tokens work with this endpoint. Looking at the handler at `server/channels/api4/channel.go:931-971`, it uses `APISessionRequired` which authenticates via Bearer token:

```bash
curl -i -H 'Authorization: Bearer <your-personal-access-token>' \
  http://localhost:8065/api/v4/users/me/channels/{channel_id}/unread
```

**Important limitations:**
1. The token's user can only query their own unread status (use `me` or their own user_id)
2. Requires `PermissionEditOtherUsers` to view other users' unreads
3. Requires `PermissionReadChannel` on the channel

## Alternative: Get All Unread Channels

The API doesn't have a single endpoint to get all unreads across all channels for a user via REST. The webapp uses websocket events and client-side state aggregation for that. You'd need to iterate over channels or use the websocket `PostUnread` event.
