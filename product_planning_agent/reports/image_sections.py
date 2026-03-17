"""
Image Section Generation for Enhanced Reports
Generates PDF-style image galleries for car comparison reports
"""

from typing import Dict, Any, List


def generate_hero_section(comparison_data: Dict[str, Any]) -> str:
    """
    Generate hero section with car images at the top of the report.

    Args:
        comparison_data: Dict mapping car names to their scraped data

    Returns:
        HTML string for hero section
    """
    car_names = []
    hero_images = []

    for car_name, car_data in comparison_data.items():
        if isinstance(car_data, dict) and "error" not in car_data:
            car_names.append(car_name)
            images = car_data.get("images") or {}
            hero_imgs = images.get("hero", [])
            if hero_imgs:
                # Handle multiple formats: list, tuple, or string
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
                hero_images.append("")  # Placeholder

    if not car_names:
        return ""

    # Generate title
    if len(car_names) == 1:
        title = f"{car_names[0].upper()} - DETAILED ANALYSIS"
    elif len(car_names) == 2:
        title = f"{car_names[0].upper()} & {car_names[1].upper()}"
    else:
        title = " | ".join([name.upper() for name in car_names[:3]])

    # Build 1:1 comparison layout
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

    html = f'''
    <div class="hero-section" id="hero-section">
        <div class="hero-content">
            <h1 class="hero-title">{title}</h1>
            <p class="hero-subtitle">2025 COMPREHENSIVE BENCHMARKING REPORT</p>
            <div class="hero-divider"></div>
            <p class="hero-description">SPEC & FEATURES COMPARISON</p>
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
    </div>
    '''

    return html


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
    /* Hero Section Styles */
    .hero-section {
        background: linear-gradient(135deg, #2E3B4E 0%, #1c2a39 100%);
        padding: 60px 40px;
        margin: -20px -20px 40px -20px;
        border-radius: 0;
        position: relative;
        overflow: hidden;
    }

    .hero-section::before {
        content: '';
        position: absolute;
        top: 0;
        right: 0;
        width: 50%;
        height: 100%;
        background: linear-gradient(135deg, rgba(221, 3, 43, 0.1) 0%, transparent 100%);
    }

    .hero-content {
        position: relative;
        z-index: 2;
        text-align: center;
        margin-bottom: 30px;
        flex-shrink: 0;
    }

    .hero-title {
        font-size: 36px;
        font-weight: 800;
        color: white;
        margin: 0 0 12px 0;
        letter-spacing: 2px;
        text-transform: uppercase;
    }

    .hero-subtitle {
        font-size: 14px;
        color: #dd032b;
        font-weight: 600;
        margin: 0 0 16px 0;
        letter-spacing: 3px;
    }

    .hero-divider {
        width: 80px;
        height: 3px;
        background: #dd032b;
        margin: 0 auto 16px auto;
    }

    .hero-description {
        font-size: 13px;
        color: rgba(255, 255, 255, 0.8);
        margin: 0;
        letter-spacing: 2px;
    }

    /* 1:1 Comparison Layout */
    .hero-comparison-container {
        position: relative;
        z-index: 2;
        display: flex;
        align-items: stretch;
        width: 100%;
        min-height: 360px;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4);
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
        min-height: 280px;
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
        font-size: 15px;
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
        width: 50px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: #1a1a1a;
        flex-shrink: 0;
        z-index: 5;
    }

    .hero-vs-badge {
        width: 40px;
        height: 40px;
        background: #dd032b;
        color: white;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 1px;
    }

    .hero-comparison-placeholder {
        width: 100%;
        height: 100%;
        min-height: 280px;
        background: rgba(255, 255, 255, 0.1);
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
        .hero-section {
            page-break-after: always;
            margin: 0;
            padding: 40px 20px;
            break-after: page;
        }

        .hero-comparison-container {
            page-break-inside: avoid;
            break-inside: avoid;
        }

        .hero-comparison-img {
            width: 100% !important;
            height: 100% !important;
            object-fit: cover !important;
            display: block;
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
        .hero-title {
            font-size: 28px;
        }

        .hero-subtitle {
            font-size: 12px;
        }

        .hero-comparison-container {
            flex-direction: column;
            min-height: auto;
        }

        .hero-vs-divider {
            width: 100%;
            height: 40px;
            flex-direction: row;
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
