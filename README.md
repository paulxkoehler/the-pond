# The Pond

A calm, two-player browser game about wood ducks (*Aix sponsa*). Pick a drake or a hen, slip into an autumn pond, and swim, dabble, call and flap your wings alongside your mate on another device. A companion of the sibling project Cormorant.

One self-contained `index.html`. No build step.

## Playing together

There are two ways the ducks find each other. The game picks one by itself.

| Where it runs | How it pairs | Notes |
| --- | --- | --- |
| Inside Claude (the artifact page) | The page's shared room | Both people need access to the page (Share menu). |
| Netlify or any other host | PeerJS, by **pond name** | Type the same pond name on both devices. A pond holds two ducks. |

On the hosted version you can share a link that fills in the pond name: `https://<site>/?pond=lakeshore`.

PeerJS uses its free public matchmaking server to introduce the two devices, then they talk directly. Most home Wi-Fi works. Some strict mobile networks block direct links; if a pair can't see each other, try both on the same Wi-Fi.

## Controls

| | Phone | Keyboard |
| --- | --- | --- |
| Swim | Drag on the left half | WASD / arrows |
| Look | Drag on the right half | Drag with the mouse, scroll to zoom |
| Dabble | Dabble button | Space |
| Call | Call button | Q |
| Flap | Flap button | F |

## Tests

`tests/two_player.py` opens two headless browsers and checks that each duck appears on the other screen, follows its movement within a few centimetres, and hears its calls and dabbles. It runs both pairing paths (a stand-in for Claude's room, and PeerJS against a local matchmaking server), then checks that a third duck is turned away and that a partner can leave and rejoin.

```sh
pip install playwright
npm i three@0.128.0 peerjs@1.5.4 peer@1.0.2
python tests/two_player.py --libs ./node_modules
```

## Built with

* three.js r128 (cdnjs)
* PeerJS 1.5.4 (unpkg)
* Web Audio for every sound: ambience, the pad, chickadees, the owl, and both duck calls
