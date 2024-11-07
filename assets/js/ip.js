async function fetchVisitorIP() {
    console.log('lbq');
    try {
        console.log('000');
        const response = await fetch('http://ip-api.com/json/?lang=zh-CN');
        console.log('123')
        const data = await response.json();
        console.log('456')
        console.log(data)
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