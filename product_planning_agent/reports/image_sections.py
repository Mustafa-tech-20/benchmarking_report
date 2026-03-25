"""
Image Section Generation for Enhanced Reports
Generates PDF-style image galleries for car comparison reports
"""

from typing import Dict, Any, List
from datetime import datetime


def generate_hero_section(comparison_data: Dict[str, Any]) -> str:
    """
    Generate cover page and hero car image pages for PDF-style report.

    Args:
        comparison_data: Dict mapping car names to their scraped data

    Returns:
        HTML string for cover page + hero image pages
    """
    car_names = []
    hero_images = []

    for car_name, car_data in comparison_data.items():
        if isinstance(car_data, dict) and "error" not in car_data:
            car_names.append(car_name)
            images = car_data.get("images") or {}
            hero_imgs = images.get("hero", [])
            if hero_imgs:
                first_img = hero_imgs[0]
                if isinstance(first_img, (list, tuple)) and len(first_img) >= 1:
                    img_url = first_img[0]
                    if img_url and isinstance(img_url, str):
                        hero_images.append(img_url)
                    else:
                        hero_images.append("")
                elif isinstance(first_img, str):
                    hero_images.append(first_img)
                else:
                    hero_images.append("")
            else:
                hero_images.append("")

    if not car_names:
        return ""

    # Generate title from car names
    title = " | ".join([name.upper() for name in car_names])

    # Current date
    current_date = datetime.now().strftime("%d.%m.%Y")

    # PAGE 1: Cover Page with geometric pattern
    cover_page = f'''
    <div class="cover-page" id="hero-section">
        <div class="cover-geometric-pattern">
            <svg viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice">
                <defs>
                    <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:#d4a574;stop-opacity:0.6" />
                        <stop offset="100%" style="stop-color:#c9956c;stop-opacity:0.3" />
                    </linearGradient>
                </defs>
                <!-- Geometric lines pattern -->
                <path d="M0 200 L400 100 L600 300 L800 150 L1000 350 L1200 200" stroke="url(#lineGradient)" stroke-width="1.5" fill="none" opacity="0.7"/>
                <path d="M0 300 L300 200 L500 400 L700 250 L900 450 L1100 300 L1200 350" stroke="url(#lineGradient)" stroke-width="1.5" fill="none" opacity="0.6"/>
                <path d="M0 400 L200 300 L450 500 L650 350 L850 550 L1050 400 L1200 450" stroke="url(#lineGradient)" stroke-width="1.5" fill="none" opacity="0.5"/>
                <path d="M100 100 L350 250 L550 150 L750 350 L950 200 L1150 400" stroke="url(#lineGradient)" stroke-width="1.5" fill="none" opacity="0.5"/>
                <path d="M50 500 L250 400 L500 550 L700 400 L950 600 L1200 500" stroke="url(#lineGradient)" stroke-width="1.5" fill="none" opacity="0.4"/>
                <!-- Angular shapes -->
                <polygon points="300,150 450,100 500,200 400,280 280,220" stroke="url(#lineGradient)" stroke-width="1.5" fill="none" opacity="0.5"/>
                <polygon points="550,200 700,150 780,280 680,380 520,320" stroke="url(#lineGradient)" stroke-width="1.5" fill="none" opacity="0.4"/>
                <polygon points="700,80 850,50 920,150 850,250 720,200" stroke="url(#lineGradient)" stroke-width="1.5" fill="none" opacity="0.45"/>
                <polygon points="400,350 550,300 620,420 540,500 380,450" stroke="url(#lineGradient)" stroke-width="1.5" fill="none" opacity="0.35"/>
            </svg>
        </div>
        <div class="cover-logo">
            <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Mahindra_logo.svg/1920px-Mahindra_logo.svg.png?_=20231128143513" alt="Mahindra">
        </div>
        <div class="cover-content">
            <h1 class="cover-title">{title}</h1>
            <h2 class="cover-subtitle">PRODUCT PLANNING<br>SOFT REPORT</h2>
            <p class="cover-date">{current_date}</p>
        </div>
    </div>
    '''

    # PAGE 2: Single side-by-side comparison page
    left_name = car_names[0]
    left_img = hero_images[0] if hero_images else ""
    right_cars = list(zip(car_names[1:], hero_images[1:]))

    left_img_tag = (
        f'<img src="{left_img}" alt="{left_name}" class="hero-comparison-img" onerror="this.style.display=\'none\'">'
        if left_img else '<div class="hero-comparison-placeholder"></div>'
    )

    right_panels_html = ""
    for rname, rimg in right_cars:
        img_tag = (
            f'<img src="{rimg}" alt="{rname}" class="hero-comparison-img" onerror="this.style.display=\'none\'">'
            if rimg else '<div class="hero-comparison-placeholder"></div>'
        )
        right_panels_html += f'''
        <div class="hero-comparison-car">
            <div class="hero-comparison-image-wrap">
                {img_tag}
            </div>
            <div class="hero-comparison-label">{rname}</div>
        </div>
        '''

    if not right_panels_html:
        right_panels_html = '<div class="hero-comparison-placeholder"></div>'

    comparison_page = f'''
    <div class="hero-image-page" id="hero-comparison">
        <div class="hero-page-header">
            <h1 class="hero-page-title">VEHICLE COMPARISON | <span class="highlight">PRODUCT PLANNING</span></h1>
            <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Mahindra_logo.svg/1920px-Mahindra_logo.svg.png?_=20231128143513" alt="Mahindra" class="hero-page-logo">
        </div>
        <div class="hero-comparison-container">
            <div class="hero-comparison-side hero-comparison-left-side">
                <div class="hero-comparison-image-wrap">
                    {left_img_tag}
                </div>
                <div class="hero-comparison-label">{left_name}</div>
            </div>
            <div class="hero-vs-divider">
                <div class="hero-vs-badge">VS</div>
            </div>
            <div class="hero-comparison-side hero-comparison-right-side">
                {right_panels_html}
            </div>
        </div>
        <div class="hero-page-footer"></div>
    </div>
    '''

    return cover_page + comparison_page


def generate_image_gallery_section(
    title: str,
    comparison_data: Dict[str, Any],
    image_category: str,
    section_id: str = ""
) -> str:
    """
    Generate an image gallery section for a specific category.

    Args:
        title: Section title (e.g., "Exterior Highlights")
        comparison_data: Dict mapping car names to their scraped data
        image_category: Category key in images dict ("exterior", "interior", etc.)
        section_id: Optional HTML id for the section

    Returns:
        HTML string for image gallery section
    """
    # Collect all images from all cars for this category
    all_images = []

    for car_name, car_data in comparison_data.items():
        if isinstance(car_data, dict) and "error" not in car_data:
            images = car_data.get("images") or {}
            category_images = images.get(image_category, [])

            # Handle multiple formats: list, tuple, or string
            for img_item in category_images:
                img_url = None
                feature_caption = image_category.title()

                if isinstance(img_item, (list, tuple)) and len(img_item) >= 1:
                    # Format: [url, caption] or (url, caption)
                    img_url = img_item[0]
                    if len(img_item) >= 2:
                        feature_caption = img_item[1]
                elif isinstance(img_item, str):
                    # Fallback for simple URL format
                    img_url = img_item

                # Add all valid image URLs
                if img_url and isinstance(img_url, str):
                    all_images.append({
                        "url": img_url,
                        "feature": feature_caption,  # e.g., "Headlights"
                        "car_name": car_name,        # e.g., "Mahindra Thar"
                        "alt": f"{car_name} {feature_caption}"
                    })

    if not all_images:
        return ""  # Don't show section if no images

    # Generate image grid
    images_html = ""
    for img_data in all_images[:12]:  # Max 12 images per section
        images_html += f'''
        <div class="gallery-item">
            <img src="{img_data['url']}" alt="{img_data['alt']}"
                 onerror="this.parentElement.style.display='none'">
            <div class="gallery-feature">{img_data['feature']}</div>
            <div class="gallery-car-name">{img_data['car_name']}</div>
        </div>
        '''

    id_attr = f'id="{section_id}"' if section_id else ""

    html = f'''
    <div class="content image-gallery-section" {id_attr}>
        <div class="section-header">
            <div class="icon-wrapper">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                    <circle cx="8.5" cy="8.5" r="1.5"/>
                    <polyline points="21 15 16 10 5 21"/>
                </svg>
            </div>
            <h2>{title}</h2>
        </div>
        <div class="image-gallery">
            {images_html}
        </div>
    </div>
    '''

    return html


def get_image_section_styles() -> str:
    """
    Returns CSS styles for image sections.
    """
    return '''
    /* ========================================
       COVER PAGE STYLES
       ======================================== */
    .cover-page {
        width: 100%;
        height: 100vh;
        min-height: 700px;
        background: #f5f5f5;
        position: relative;
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
        padding: 60px;
        box-sizing: border-box;
        page-break-after: always;
        break-after: page;
    }

    .cover-geometric-pattern {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        overflow: hidden;
        z-index: 1;
    }

    .cover-geometric-pattern svg {
        width: 100%;
        height: 100%;
    }

    .cover-logo {
        position: absolute;
        top: 40px;
        right: 60px;
        z-index: 10;
    }

    .cover-logo img {
        height: 28px;
        width: auto;
        filter: brightness(0);
    }

    .cover-content {
        position: relative;
        z-index: 10;
        text-align: right;
        padding-right: 20px;
    }

    .cover-title {
        font-size: 38px;
        font-weight: 800;
        color: #1a1a1a;
        margin: 0 0 10px 0;
        letter-spacing: 1px;
        line-height: 1.2;
    }

    .cover-subtitle {
        font-size: 32px;
        font-weight: 700;
        color: #1a1a1a;
        margin: 0 0 30px 0;
        letter-spacing: 0.5px;
        line-height: 1.3;
    }

    .cover-date {
        font-size: 16px;
        font-weight: 500;
        color: #0066cc;
        margin: 0;
    }

    /* ========================================
       HERO COMPARISON PAGE STYLES
       ======================================== */
    .hero-image-page {
        width: 100%;
        height: 100vh;
        min-height: 700px;
        background: #ffffff;
        position: relative;
        display: flex;
        flex-direction: column;
        page-break-after: always;
        break-after: page;
        box-sizing: border-box;
    }

    .hero-page-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 24px 50px;
    }

    .hero-page-title {
        font-size: 22px;
        font-weight: 400;
        color: #333;
        margin: 0;
        letter-spacing: 1px;
    }

    .hero-page-title .highlight {
        color: #0066cc;
        font-weight: 600;
    }

    .hero-page-logo {
        height: 24px;
        width: auto;
        filter: brightness(0);
    }

    .hero-comparison-container {
        flex: 1;
        display: flex;
        align-items: stretch;
        overflow: hidden;
        min-height: 0;
    }

    .hero-comparison-side {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        min-width: 0;
    }

    .hero-comparison-image-wrap {
        flex: 1;
        overflow: hidden;
        position: relative;
        min-height: 0;
    }

    .hero-comparison-img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
    }

    .hero-comparison-label {
        padding: 14px 20px;
        text-align: center;
        font-size: 16px;
        font-weight: 700;
        color: #1a1a1a;
        background: #f0f0f0;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        flex-shrink: 0;
    }

    .hero-comparison-left-side .hero-comparison-label {
        background: #1a1a1a;
        color: #ffffff;
    }

    .hero-comparison-right-side {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        min-width: 0;
    }

    .hero-comparison-car {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        min-height: 0;
    }

    .hero-vs-divider {
        width: 56px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: #1a1a1a;
        flex-shrink: 0;
        z-index: 5;
    }

    .hero-vs-badge {
        width: 44px;
        height: 44px;
        background: #cc0000;
        color: white;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 13px;
        font-weight: 800;
        letter-spacing: 1px;
    }

    .hero-comparison-placeholder {
        width: 100%;
        height: 100%;
        background: #e8e8e8;
    }

    .hero-page-footer {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        padding: 16px 50px 24px;
        border-top: 4px solid #1a1a1a;
        margin: 0 50px;
        flex-shrink: 0;
    }

    /* Image Gallery Section Styles */
    .image-gallery-section {
        margin-top: 40px;
    }

    .image-gallery {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 25px;
        padding: 20px 0;
    }

    .gallery-item {
        background: white;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        cursor: pointer;
    }

    .gallery-item:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
    }

    .gallery-item img {
        width: 100%;
        height: 200px;
        object-fit: cover;
        display: block;
    }

    .gallery-feature {
        padding: 12px 15px 8px 15px;
        text-align: center;
        font-size: 13px;
        font-weight: 700;
        color: #1c2a39;
        background: #f8f9fa;
        line-height: 1.3;
    }

    .gallery-car-name {
        padding: 0 15px 12px 15px;
        text-align: center;
        font-size: 11px;
        font-weight: 500;
        color: #6c757d;
        background: #f8f9fa;
    }

    /* Print Styles for Images */
    @media print {
        .cover-page {
            page-break-after: always !important;
            break-after: page !important;
            height: 100vh !important;
            min-height: 100vh !important;
        }

        .hero-image-page {
            page-break-after: always !important;
            break-after: page !important;
            height: 100vh !important;
            min-height: 100vh !important;
        }

        .hero-comparison-img {
            width: 100% !important;
            height: 100% !important;
            object-fit: cover !important;
        }

        .hero-section {
            page-break-after: always;
            margin: 0;
            padding: 40px 20px;
            break-after: page;
        }

        .hero-car-card {
            page-break-inside: avoid;
            break-inside: avoid;
        }

        .hero-car-card img {
            width: 100% !important;
            height: auto !important;
            max-height: 200px !important;
            object-fit: contain !important;
            display: block;
            margin: 0 auto;
        }

        .image-gallery {
            display: grid !important;
            grid-template-columns: repeat(2, 1fr) !important;
            gap: 10px !important;
            page-break-inside: auto !important;
        }

        .gallery-item {
            page-break-inside: avoid !important;
            break-inside: avoid !important;
            margin-bottom: 10px !important;
            box-shadow: none !important;
            border: 1px solid #ddd !important;
        }

        /* Force page break after every 6 items (2x3 grid) */
        .gallery-item:nth-child(6n) {
            page-break-after: always !important;
            break-after: page !important;
        }

        .gallery-item img {
            width: 100% !important;
            height: 180px !important;
            max-height: 180px !important;
            object-fit: contain !important;
            display: block;
            margin: 0 auto;
            background: #f8f9fa;
        }

        .image-gallery-section {
            page-break-before: auto;
            page-break-after: auto;
            page-break-inside: auto;
            break-before: auto;
            break-after: auto;
            break-inside: auto;
            margin-bottom: 0;
        }

        .section-header {
            page-break-after: avoid;
            break-after: avoid;
        }

        .gallery-feature,
        .gallery-car-name {
            page-break-inside: avoid !important;
            break-inside: avoid !important;
            text-align: center;
            font-size: 10px !important;
            padding: 6px 8px !important;
        }
    }

    /* Mobile Responsive */
    @media (max-width: 768px) {
        .cover-page {
            padding: 30px;
            height: auto;
            min-height: 100vh;
        }

        .cover-title {
            font-size: 28px;
        }

        .cover-subtitle {
            font-size: 22px;
        }

        .cover-logo {
            top: 20px;
            right: 30px;
        }

        .hero-page-header {
            flex-direction: column;
            gap: 15px;
            padding: 20px;
        }

        .hero-page-title {
            font-size: 16px;
        }

        .hero-comparison-container {
            flex-direction: column;
        }

        .hero-vs-divider {
            width: 100%;
            height: 40px;
            flex-direction: row;
        }

        .hero-title {
            font-size: 28px;
        }

        .hero-subtitle {
            font-size: 12px;
        }

        .hero-images-grid {
            grid-template-columns: 1fr;
            gap: 20px;
        }

        .image-gallery {
            grid-template-columns: 1fr;
            gap: 15px;
        }

        .gallery-item img {
            height: 180px;
        }
    }
    '''
