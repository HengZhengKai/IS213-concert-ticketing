async function fetchEvents() {
    console.log("Fetching events...");
    
    // Return hardcoded events first
    let hardcodedEvents = [
        { id: 1, name: "Concert Night", date: "2025-04-10" },
        { id: 2, name: "Tech Conference", date: "2025-05-20" },
        { id: 3, name: "Sports Championship", date: "2025-06-15" }
    ];
    
    try {
        let res = await fetch("http://localhost:5001/events");
        let data = await res.json();
        console.log("Received events:", data);
        return data; // Return actual data from backend
    } catch (error) {
        console.error("Error fetching events:", error);
        return hardcodedEvents; // Return hardcoded if API fails
    }
}


async function fetchAvailableTickets() {
    let res = await fetch("http://localhost:5002/tickets");
    return res.json();
}

async function buyTicketAPI(ticketID) {
    let res = await fetch(`http://localhost:5002/buyticket/${ticketID}`, { method: "POST" });
    return (await res.json()).message;
}

async function buyResaleAPI(ticketID) {
    let res = await fetch(`http://localhost:5002/buyresaleticket/${ticketID}`, { method: "POST" });
    return (await res.json()).message;
}

async function resellTicketAPI(ticketID, price) {
    let res = await fetch(`http://localhost:5002/resellticket`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticketID, price })
    });
    return (await res.json()).message;
}

async function checkInAPI(ticketID) {
    let res = await fetch(`http://localhost:5002/checkin/${ticketID}`, { method: "POST" });
    return (await res.json()).message;
}
