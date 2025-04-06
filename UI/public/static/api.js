// Helper function for delaying execution
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

async function fetchEvents(retries = 3, delayMs = 500) {
    console.log(`Fetching events... Attempt ${4 - retries}`);

    try {
        // NOTE: Changed URL to target event_service directly based on docker-compose
        const response = await fetch("http://localhost:5001/event"); 
        
        if (!response.ok) {
            // Throw an error for bad HTTP status codes
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log("Received events data structure:", data);
        
        // Assuming the event service returns { "code": 200, "data": { "events": [...] } }
        if (data.code === 200 && data.data && Array.isArray(data.data.events)) {
            console.log("Events fetched successfully:", data.data.events);
            // Transform the data to match the format expected by the frontend
            return data.data.events.map(event => {
                // Check both possible field names
                const rawImageData = event.imageBase64 || event.displayPicture || '';
                
                // Properly format the image data with prefix if needed
                const imageData = rawImageData.startsWith('data:') ? 
                                rawImageData : 
                                rawImageData ? `data:image/png;base64,${rawImageData}` : '';
                
                // Format the date more nicely for display
                let formattedDate = 'No date available';
                if (event.dates && event.dates.length > 0 && event.dates[0].eventDateTime) {
                    try {
                        const dateObj = new Date(event.dates[0].eventDateTime);
                        formattedDate = dateObj.toLocaleDateString('en-SG', {
                            year: 'numeric', month: 'long', day: 'numeric',
                            hour: '2-digit', minute: '2-digit'
                        });
                    } catch (e) {
                        console.error("Date formatting error:", e);
                    }
                } else {
                    console.warn("Event missing dates or eventDateTime:", event.eventID);
                }
                
                const allDates = [];
                if (event.dates && Array.isArray(event.dates)) {
                    event.dates.forEach(date => {
                        try {
                            const dateObj = new Date(date.eventDateTime);
                            allDates.push({
                                eventDateTime: date.eventDateTime, 
                                formatted: dateObj.toLocaleDateString('en-SG', {
                                    year: 'numeric', month: 'long', day: 'numeric',
                                    hour: '2-digit', minute: '2-digit'
                                }),
                                availableSeats: date.availableSeats
                            });
                        } catch (e) {
                            console.error("Date processing error:", e);
                        }
                    });
                }

                return {
                    id: event.eventID || 'N/A',
                    name: event.eventName || 'Unknown Event',
                    imageBase64: imageData,
                    venue: event.venue || 'Unknown Venue',
                    description: event.description || 'No description',
                    date: formattedDate,
                    totalSeats: event.totalSeats || 0,
                    availableSeats: event.dates && event.dates.length > 0 ? 
                                    event.dates[0].availableSeats : 
                                    'Unknown',
                    allDates: allDates
                };
            });
        } else {
            console.error("Invalid data format received from event service:", data);
            throw new Error("Invalid data format received"); 
        }
    } catch (error) {
        console.error(`Error fetching events (Attempt ${4 - retries}):`, error);
        if (retries > 1) {
            console.log(`Retrying in ${delayMs}ms...`);
            await delay(delayMs);
            return fetchEvents(retries - 1, delayMs); // Recursive call to retry
        } else {
            console.error("Max retries reached. Returning fallback data.");
            // Return hardcoded events as fallback only after all retries fail
            return [
                { id: "E001", name: "Wrong Event", date: "2025-10-05", venue: "The Arena, Singapore" },
                { id: "E002", name: "Kpop Stars Live", date: "2025-06-15", venue: "Marina Bay Sands Expo" }
            ];
        }
    }
}

async function fetchAvailableTickets() {
    let res = await fetch("http://localhost:5001/ticket");
    return res.json();
}

async function buyTicketAPI(ticketID) {
    let res = await fetch(`http://localhost:5001/buyticket/${ticketID}`, { method: "POST" });
    return (await res.json()).message;
}

async function buyResaleAPI(ticketID) {
    let res = await fetch(`http://localhost:5001/buyresaleticket/${ticketID}`, { method: "POST" });
    return (await res.json()).message;
}

async function resellTicketAPI(ticketID, price) {
    let res = await fetch(`http://localhost:5001/resellticket`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticketID, price })
    });
    return (await res.json()).message;
}

async function checkInAPI(ticketID) {
    let res = await fetch(`http://localhost:5001/checkin/${ticketID}`, { method: "POST" });
    return (await res.json()).message;
}
