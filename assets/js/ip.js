async function fetchVisitorIP() {
    try {
        const ipData = await fetch('https://api.ipify.org?format=json');
        const ip = await ipData.json();
        const response = await fetch(`https://ip.xinhaidong.top?ip=${ip.ip}`);
        const data = await response.json();
        if (data) {
            document.getElementById('visitor-ip').textContent = `${data.query}`;
            document.getElementById('visitor-address').textContent = `${data.country} ${data.regionName} ${data.city}`;
        } else {
            document.getElementById('visitor-ip').textContent = "error";
            document.getElementById('visitor-address').textContent = "error";
        }
    } catch (error) {
        document.getElementById('visitor-ip').textContent = "error";
        document.getElementById('visitor-address').textContent = "error";
        console.error("Error fetching IP data:", error);
    }
}

document.addEventListener('DOMContentLoaded', fetchVisitorIP);