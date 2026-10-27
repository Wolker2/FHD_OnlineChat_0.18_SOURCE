#ifndef FHD_CHAT_EVENT_H
#define FHD_CHAT_EVENT_H
/* Internal x86 ABI, shared by the network bridge and in-frame UI. */
typedef struct {
 WCHAR nick[36],text[512],peer[36];
 char peerId[80];
 int own,channel,event;
 DWORD day;
 char senderId[80];
} FHDChatEvent;
#endif
