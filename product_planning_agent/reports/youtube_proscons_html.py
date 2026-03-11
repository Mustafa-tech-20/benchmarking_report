"""
HTML Generator for YouTube Pros & Cons Report
Generates a professional HTML report for car reviews from YouTube channels
"""

from typing import Dict, List, Any


def create_youtube_proscons_html(proscons_data: Dict[str, List[Dict[str, Any]]]) -> str:
    """
    Create an HTML report for YouTube pros/cons data.

    Args:
        proscons_data: Dictionary mapping car names to list of pros/cons from different channels
                      Format: {
                          "Car Name": [
                              {
                                  "car_name": "Car Name",
                                  "publication": "Channel Name",
                                  "video_title": "Video Title",
                                  "link": "YouTube search URL",
                                  "positives": ["pos1", "pos2", ...],
                                  "negatives": ["neg1", "neg2", ...]
                              },
                              ...
                          ]
                      }

    Returns:
        HTML string
    """

    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Pros & Cons Analysis</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            line-height: 1.6;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        .header {
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            text-align: center;
        }

        .header h1 {
            font-size: 2.5em;
            color: #333;
            margin-bottom: 10px;
        }

        .header p {
            color: #666;
            font-size: 1.1em;
        }

        .car-section {
            background: white;
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }

        .car-title {
            font-size: 2em;
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 3px solid #667eea;
        }

        .channel-review {
            margin-bottom: 40px;
            padding: 25px;
            background: #f8f9fa;
            border-radius: 15px;
            border-left: 5px solid #667eea;
        }

        .channel-review:last-child {
            margin-bottom: 0;
        }

        .channel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 10px;
        }

        .channel-name {
            font-size: 1.5em;
            color: #667eea;
            font-weight: 600;
        }

        .video-link {
            background: #667eea;
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 500;
            transition: all 0.3s ease;
            display: inline-block;
        }

        .video-link:hover {
            background: #764ba2;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }

        .video-title {
            color: #666;
            font-size: 0.95em;
            margin-bottom: 20px;
            font-style: italic;
        }

        .pros-cons-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 25px;
            margin-top: 20px;
        }

        @media (max-width: 968px) {
            .pros-cons-container {
                grid-template-columns: 1fr;
            }
        }

        .pros-section, .cons-section {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 3px 10px rgba(0,0,0,0.05);
        }

        .pros-section {
            border-left: 4px solid #10b981;
        }

        .cons-section {
            border-left: 4px solid #ef4444;
        }

        .section-title {
            font-size: 1.3em;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .pros-title {
            color: #10b981;
        }

        .cons-title {
            color: #ef4444;
        }

        .icon {
            font-size: 1.2em;
        }

        .point-list {
            list-style: none;
        }

        .point-item {
            padding: 12px;
            margin-bottom: 10px;
            background: #f9fafb;
            border-radius: 8px;
            position: relative;
            padding-left: 35px;
        }

        .point-item:before {
            content: "•";
            position: absolute;
            left: 15px;
            font-size: 1.5em;
            font-weight: bold;
        }

        .pros-section .point-item:before {
            color: #10b981;
        }

        .cons-section .point-item:before {
            color: #ef4444;
        }

        .summary-box {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 15px;
            margin-top: 30px;
            text-align: center;
        }

        .summary-box h3 {
            font-size: 1.5em;
            margin-bottom: 10px;
        }

        .note {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin-top: 20px;
            border-radius: 8px;
            font-size: 0.9em;
            color: #856404;
        }

        .footer {
            text-align: center;
            color: white;
            margin-top: 30px;
            padding: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎬 YouTube Pros & Cons Analysis</h1>
            <p>Professional automotive reviews from trusted Indian YouTube channels</p>
        </div>
"""

    # Add each car's data
    for car_name, reviews in proscons_data.items():
        html += f"""
        <div class="car-section">
            <h2 class="car-title">{car_name}</h2>
"""

        # Add each channel's review for this car
        for review in reviews:
            if not review or not isinstance(review, dict):
                continue
            channel = review.get('publication', 'N/A')
            video_title = review.get('video_title', 'N/A')
            link = review.get('link', '#')
            positives = review.get('positives') or []
            negatives = review.get('negatives') or []

            html += f"""
            <div class="channel-review">
                <div class="channel-header">
                    <div class="channel-name">📺 {channel}</div>
                    <a href="{link}" target="_blank" class="video-link">🔍 Find Video</a>
                </div>
                <div class="video-title">{video_title}</div>

                <div class="pros-cons-container">
                    <div class="pros-section">
                        <h3 class="section-title pros-title">
                            <span class="icon">✓</span>
                            Positives ({len(positives)})
                        </h3>
                        <ul class="point-list">
"""
            for positive in positives:
                html += f'                            <li class="point-item">{positive}</li>\n'

            html += """
                        </ul>
                    </div>

                    <div class="cons-section">
                        <h3 class="section-title cons-title">
                            <span class="icon">✗</span>
                            Negatives ({})
                        </h3>
                        <ul class="point-list">
""".format(len(negatives))

            for negative in negatives:
                html += f'                            <li class="point-item">{negative}</li>\n'

            html += """
                        </ul>
                    </div>
                </div>
            </div>
"""

        html += """
        </div>
"""

    # Add footer with note
    html += """
        <div class="note">
            <strong>💡 Note:</strong> Links provided are YouTube search URLs that help you find the actual review videos.
            Click "Find Video" to search for the specific review on YouTube. This ensures you always get access to the
            most relevant and recent content from these trusted automotive channels.
        </div>

        <div class="footer">
            <p>Generated using Gemini AI • Analyzed from trusted automotive YouTube channels</p>
            <p style="margin-top: 10px; font-size: 0.9em;">No API quotas • Direct AI analysis • Always up-to-date</p>
        </div>
    </div>
</body>
</html>
"""

    return html


def save_youtube_proscons_html(proscons_data: Dict[str, List[Dict[str, Any]]], filename: str = "youtube_proscons_report.html") -> str:
    """
    Create and save YouTube pros/cons HTML report to file.

    Args:
        proscons_data: Dictionary mapping car names to their pros/cons from different channels
        filename: Output filename (default: youtube_proscons_report.html)

    Returns:
        Path to saved HTML file
    """
    html_content = create_youtube_proscons_html(proscons_data)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return filename
