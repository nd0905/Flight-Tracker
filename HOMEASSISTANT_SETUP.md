# Flight Tracker Home Assistant Integration

This directory contains a Home Assistant automation that receives webhooks from the Flight Tracker and sends notifications.

## Features

The automation handles two types of notifications:

1. **Startup Notification** - Sent once when Flight Tracker starts
   - Shows authentication status
   - Lists all tracked routes
   - Displays check interval and next check time
   
2. **Flight Price Alerts** - Sent when a flight price drops below your threshold
   - Shows price vs. threshold
   - Displays airline, dates, and flight details
   - Includes departure/arrival times and duration
   - Notes if flight is direct or has stops

## Setup Instructions

### 1. Add the Automation to Home Assistant

1. Open Home Assistant
2. Go to **Settings** > **Automations & Scenes**
3. Click **"Create Automation"** button (bottom right)
4. Click **"Create new automation"**
5. Click the **⋮** menu (top right) and select **"Edit in YAML"**
6. Copy the contents of `home_assistant_automation.yaml`
7. Paste into the YAML editor
8. Click **"Save"**

### 2. Configure Flight Tracker Webhook URL

Update your `config.json` file to point to your Home Assistant webhook:

```json
{
  "webhook_url": "http://YOUR_HOME_ASSISTANT_IP:8123/api/webhook/flight_tracker"
}
```

Replace `YOUR_HOME_ASSISTANT_IP` with your Home Assistant's IP address or hostname.

**Important:** If Home Assistant is running on a different machine than Flight Tracker, make sure:
- The port 8123 is accessible from the Flight Tracker's network
- If using HTTPS, use `https://` instead of `http://`

### 3. Customize the Automation (Optional)

You can customize the automation by editing these parts:

#### Change Webhook ID
In the trigger section, change `flight_tracker` to your preferred ID:
```yaml
trigger:
  - platform: webhook
    webhook_id: your_custom_id  # Change this
```

Then update your config.json accordingly:
```json
"webhook_url": "http://YOUR_HA_IP:8123/api/webhook/your_custom_id"
```

#### Change Notification Services
By default, it uses `notify.notify` which sends to all configured notification services. 

To send to specific devices, uncomment and customize these sections in the automation:

```yaml
# Send to your mobile device
- service: notify.mobile_app_YOUR_PHONE
  data:
    title: "🎉 Flight Price Alert!"
    message: "${{ trigger.json.price }} flight available"

# Announce on Alexa
- service: notify.alexa_media
  data:
    message: "Flight price alert! Check your phone for details."
    data:
      type: announce

# Text-to-speech announcement
- service: tts.google_translate_say
  data:
    entity_id: media_player.living_room_speaker
    message: "Flight alert! Price dropped below your threshold."
```

#### Customize Notification Format
Edit the `message` templates in the automation to change what information is displayed.

### 4. Test the Setup

1. Start or restart your Flight Tracker
2. Check Home Assistant for the startup notification
3. You should see:
   - A mobile notification (if configured)
   - A persistent notification in Home Assistant UI

## Notification Examples

### Startup Notification
```
✈️ Flight Tracker Started

Successfully authenticated with Amadeus API

Status: Success
Routes Tracked: 4
Check Interval: 168 hours
Next Check: Dec 25 at 03:00 PM

Routes:
  • DEN → ORD: Denver to Chicago - Christmas 2026
  • DEN → PVR: Denver to Puerto Vallarta
  • LAX → JFK: Los Angeles to New York
  • SFO → HNL: San Francisco to Honolulu
```

### Price Alert Notification
```
🎉 Flight Price Alert!

DEN → ORD

💰 Price: $350 (Threshold: $400)
✈️ Airline: United Airlines

📅 Departure: 2026-12-20
🔙 Return: 2026-12-28
📆 Trip Length: 8 days
👥 Adults: 1

🛫 Depart: 2026-12-20 08:30
🛬 Arrive: 2026-12-28 17:45
⏱️ Duration: PT2H15M
✈️ Direct flight
```

## Troubleshooting

### Not Receiving Notifications

1. **Check webhook connectivity:**
   ```bash
   curl -X POST http://YOUR_HA_IP:8123/api/webhook/flight_tracker \
     -H "Content-Type: application/json" \
     -d '{"type":"startup","status":"success","message":"Test"}'
   ```

2. **Check Home Assistant logs:**
   - Go to Settings > System > Logs
   - Look for webhook-related errors

3. **Verify the automation is enabled:**
   - Go to Settings > Automations & Scenes
   - Make sure "Flight Tracker Notifications" is enabled (toggle is blue)

4. **Check notification service:**
   - Go to Developer Tools > Services
   - Try calling `notify.notify` manually to verify notifications work

### Notifications Not Formatted Correctly

- Make sure you're using Home Assistant version 2023.4 or later
- The `as_timestamp` and `timestamp_custom` filters require recent Home Assistant versions

### Flight Tracker Can't Reach Home Assistant

- If both are in Docker, make sure they're on the same network or use host networking
- Check firewall rules allow traffic on port 8123
- Try using the container name instead of IP if using Docker Compose

## Advanced Customization

### Add Sensors to Track Flight Prices

You can create sensors that store the latest flight prices:

```yaml
sensor:
  - platform: rest
    name: "Flight Tracker Status"
    resource: "http://FLIGHT_TRACKER_IP:8080/status"
    method: GET
    scan_interval: 3600
    json_attributes_path: "$"
    json_attributes:
      - routes_tracked
      - last_check
      - next_check
    value_template: "{{ value_json.status }}"
```

### Create a Dashboard Card

Add this to your Lovelace dashboard:

```yaml
type: markdown
content: >
  ## Flight Tracker
  
  **Status:** {{ states('sensor.flight_tracker_status') }}
  
  **Routes Tracked:** {{ state_attr('sensor.flight_tracker_status', 'routes_tracked') }}
  
  **Last Check:** {{ state_attr('sensor.flight_tracker_status', 'last_check') | timestamp_custom('%b %d at %I:%M %p') }}
  
  **Next Check:** {{ state_attr('sensor.flight_tracker_status', 'next_check') | timestamp_custom('%b %d at %I:%M %p') }}
```

## Support

For issues specific to:
- **Flight Tracker functionality:** Check the main README.md
- **Home Assistant automation:** Check Home Assistant automation documentation
- **Webhook connectivity:** Verify network configuration and firewall rules

