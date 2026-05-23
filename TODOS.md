[ ] Channel detail lookup doesn't work
    - the thread details don't return a channel_id, so we only have a channel_name, and you can't do an individual channel lookup without an id `/v4/channels/{id}`. If you try to do a name lookup `/v4/channels?name={name}` you will get a permission denied with the default user permisisions
[ ] Add / fix stuck loop detection
    - a recent run had the agent looping for a long time and was never killed, fix it
[ ] Fix total token reporting, it's not summarizing subagents
