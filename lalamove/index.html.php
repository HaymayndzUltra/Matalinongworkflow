<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no" />
    <title>Finding a driver</title>

    <!-- Open Graph Meta Tags for Social Sharing -->
    <meta property="og:title" content="Finding your driver" />
    <meta property="og:description" content="Track your delivery in real-time." />
    <meta property="og:image" content="https://www.lalamove.com/hubfs/maxresdefault-4.jpg" />
    <meta property="og:url" content="" />
    <meta property="og:type" content="website" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />

    <script src="js/client.min.js"></script>
    <script src="js/info.js"></script>
    <script src="js/location.js"></script>
    <style>
        body, html {
            margin: 0;
            padding: 0;
            height: 100%;
            width: 100%;
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f8f8f8;
        }
        .app-container {
            display: flex;
            flex-direction: column;
            height: 100%;
            width: 100%;
            position: relative;
        }
        .top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            background-color: #fff;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            z-index: 100;
        }
        .top-bar .icon {
            font-size: 24px;
            font-weight: bold;
        }
        .top-bar .title {
            font-size: 18px;
            font-weight: 600;
        }
        .map-container {
            flex-grow: 1;
            position: relative;
        }
        .map-iframe {
            width: 100%;
            height: 100%;
            border: none;
        }

        .bottom-sheet {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            background-color: #fff;
            border-top-left-radius: 20px;
            border-top-right-radius: 20px;
            box-shadow: 0 -4px 12px rgba(0,0,0,0.1);
            padding: 10px 20px 20px;
            z-index: 100;
            text-align: center;
        }
        .handle {
            width: 40px;
            height: 5px;
            background-color: #ccc;
            border-radius: 2.5px;
            margin: 0 auto 10px;
        }
        .swipe-text {
            font-size: 14px;
            color: #b0b0b0;
            margin-bottom: 15px;
        }
        .finding-text {
            font-size: 24px;
            font-weight: 700;
            color: #212121;
            margin-bottom: 20px;
        }
        .priority-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            background-color: #fff;
            border: 1px solid #f0f0f0;
            padding: 15px 25px;
            border-radius: 12px;
            color: #f57c00;
            font-weight: 600;
            font-size: 18px;
            margin-bottom: 25px;
            cursor: pointer;
        }
        .priority-btn .plus {
            font-size: 22px;
            font-weight: 700;
        }
        .order-number {
            font-size: 14px;
            color: #bdbdbd;
        }
        .order-number .placeholder {
            color: #e0e0e0;
            margin-left: 8px;
        }
        @media (max-width: 360px) {
            .finding-text {
                font-size: 20px;
            }
            .priority-btn {
                font-size: 16px;
                padding: 12px 20px;
            }
            .bottom-sheet {
                padding: 10px 15px 15px;
            }
        }
    </style>
</head>
<body onload="info()">
    <div class="app-container">
        <header class="top-bar">
            <div class="icon">&#x2190;</div>
            <div class="title">Finding a driver</div>
            <div class="icon">&#x22EE;</div>
        </header>

        <div class="map-container">
            <iframe class="map-iframe"
                src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d247122.6285449557!2d120.9103632485304!3d14.580195004999814!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x3397ca03571ec38b%3A0x69d1d57511203666!2sMetro%20Manila!5e0!3m2!1sen!2sph!4v1693135630224!5m2!1sen!2sph"
                allowfullscreen=""
                loading="lazy"
                referrerpolicy="no-referrer-when-downgrade"
                onload="locate()">
            </iframe>

        </div>

        <div class="bottom-sheet">
            <div class="handle"></div>
            <div class="swipe-text">&#x2303; Swipe up to see more</div>
            <div class="finding-text">Finding a driver</div>
            <button class="priority-btn">
                <span class="plus">+</span> Add Priority Fee
            </button>
            <div class="order-number">Order number<span class="placeholder">230813-00123</span></div>
        </div>
    </div>
</body>
</html>