def build_reuse_map(chain):
    marked = set()
    heads = set()
    map_pre = {}
    for start, end in chain:
        if start in map_pre:
            map_pre[start].append(end)
        else:
            map_pre[start] = [end]
            if start not in marked:
                heads.add(start)
        if end in heads:
            heads.remove(end)
        marked.add(end)
    #print(map_pre)

    map_post = {}
    for h in heads:
        map_post[h] = []
        stack = list(reversed(map_pre[h]))
        while len(stack) > 0:
            node = stack.pop()
            map_post[h].append(node)
            if node in map_pre:
                stack.extend(reversed(map_pre[node]))
    #print(map_post)

    return map_post
