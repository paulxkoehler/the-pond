# The Pond

A calm, two-player browser game about wood ducks (*Aix sponsa*). Pick a drake or a hen, slip into an autumn pond about 140 m across (with an inlet creek, two islands and an oak point), and swim, dabble, call and flap alongside your mate on another device. Like real wood ducks, you can waddle a few metres up the bank and perch on logs, a leaning snag, rocks, a stump and the nest box. A companion of the sibling project Cormorant.

One self-contained `index.html`. No build step.

## Play

* GitHub Pages: https://paulxkoehler.github.io/the-pond/
* Netlify: https://the-pond-ducks.netlify.app/

Add `?pond=<name>` to share a pond, e.g. `https://paulxkoehler.github.io/the-pond/?pond=lakeshore`.

## Playing together

There are two ways the ducks find each other. The game picks one by itself.

| Where it runs | How it pairs | Notes |
| --- | --- | --- |
| Inside Claude (the artifact page) | The page's shared room | Both people need access to the page (Share menu). |
| Netlify or any other host | A public relay, by **pond name** | Type the same pond name on both devices. |

On the hosted version you can share a link that fills in the pond name: `https://<site>/?pond=lakeshore`.

On the hosted version, each duck's position goes through a free public MQTT broker (HiveMQ, with EMQX and Mosquitto as fallbacks) over a secure websocket. Because everything is relayed, it works across any two networks: home Wi-Fi, cellular, or one of each. The pond name is the channel, so pick something unlikely (`koehler-lakeshore`, not `test`). Only duck positions and actions travel; there are no names or accounts.

An earlier version tried direct device-to-device links (PeerJS). Those failed between real phones and laptops on different networks, so it was replaced.

## Wood duck behaviours

* **Perching:** wood ducks are among the few ducks with claws for perching. Hop onto the log, the leaning snag, the island rock, the oak stump or the nest box.
* **Foraging:** acorns are a big part of their autumn diet. Peck them up under the oaks on the oak point (they regrow after a couple of minutes).
* **Preening:** preen when perched; beside your mate, preen each other. Both preening at once is a mutual preen.
* **Courtship:** pairs form in autumn. A drake calling near a hen bobs his head, then turns the back of his crest toward her.
* **Flushing:** double-tap Flap to take off with an alarm call and fly to open water. Your mate (and the wild companion, when you're solo) follows you in the air.
* **Roosting:** at dusk and night, a duck that sits still tucks its head onto its back.

Add `?time=0.8` to the URL to jump to dusk on that device (handy for seeing the roost; it puts your sky out of step with your mate's).

## Controls

| | Phone | Keyboard |
| --- | --- | --- |
| Swim | Drag on the left half | WASD / arrows |
| Look | Drag on the right half | Drag with the mouse, scroll to zoom |
| Dabble (water) · Forage (land) · Preen (perched or beside your mate) | Main button, which changes with where you are | Space |
| Call | Call button | Q |
| Flap | Flap button | F |
| Fly (flush to open water) | Double-tap Flap | F F |
| Perch / hop down | Perch button (appears near a log, snag, rock, stump or the nest box) | E |

## Tests

`tests/two_player.py` opens two headless browsers and checks that each duck appears on the other screen, follows its movement within a few centimetres, and hears its calls and dabbles. It runs both pairing paths (a stand-in for Claude's room, and the relay against a local broker), then checks that a third duck sees both others, that different pond names stay separate, and that a partner can leave and rejoin.

```sh
pip install playwright
npm i three@0.128.0 mqtt@5.10.1 aedes@0.51.3 aedes-server-factory@0.2.1
python tests/two_player.py --libs ./node_modules
```

## Built with

* three.js r128 (cdnjs)
* MQTT.js 5.10.1 (unpkg)
* Web Audio for every sound: ambience, the pad, chickadees, the owl, and both duck calls
