async function fetchEvents() {
    console.log("Fetching events...");

    try {
        // Note: Using the correct endpoint from your Kong API Gateway
        let res = await fetch("http://127.0.0.1:5001/event");
        let data = await res.json();
        console.log("Received events:", data);
        
        if (data.code === 200 && data.data && data.data.events) {
            // Transform the data to match the format expected by the frontend
            return data.data.events.map(event => {
                // Check both possible field names
                console.log("Raw event data:", event);
                console.log("Mapped id:", event.eventID);
                const rawImageData = event.imageBase64 || event.displayPicture || '';
                
                // Properly format the image data with prefix if needed
                const imageData = rawImageData.startsWith('data:') ? 
                                rawImageData : 
                                rawImageData ? `data:image/png;base64,${rawImageData}` : '';
                
                // Format the date more nicely for display
                let formattedDate = 'No date available';
                if (event.dates && event.dates.length > 0) {
                    try {
                    const dateObj = new Date(event.dates[0].eventDateTime);
                    formattedDate = dateObj.toLocaleDateString('en-SG', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                    } catch (e) {
                        console.error("Date formatting error:", e);
                    }
                }
                
                
                const allDates = [];
                if (event.dates && Array.isArray(event.dates)) {
                    event.dates.forEach(date => {
                        try {
                            const dateObj = new Date(date.eventDateTime);
                            allDates.push({
                                eventDateTime: date.eventDateTime,  // Add this line
                                formatted: dateObj.toLocaleDateString('en-SG', {
                                    year: 'numeric',
                                    month: 'long',
                                    day: 'numeric',
                                    hour: '2-digit',
                                    minute: '2-digit'
                                }),
                                availableSeats: date.availableSeats
                            });
                        } catch (e) {
                            console.error("Date processing error:", e);
                        }
                    });
                }

                return {
                    id: event.eventID,
                    name: event.eventName,
                    imageBase64: imageData,
                    venue: event.venue,
                    description: event.description,
                    // date: event.dates && event.dates.length > 0 ? 
                    //     new Date(event.dates[0].eventDateTime).toISOString().split('T')[0] : 
                    //     'No date available',
                    date: formattedDate,
                    totalSeats: event.totalSeats,
                    availableSeats: event.dates && event.dates.length > 0 ? 
                                    event.dates[0].availableSeats : 
                                    'Unknown',
                    allDates: allDates
                };
            });
        } else {
            throw new Error("Invalid data format received");
        }
    } catch (error) {
        console.error("Error fetching events:", error);
        // Return hardcoded events as fallback
        return [
            { id: "E001", name: "Wrong Event", date: "2025-10-05", venue: "The Arena, Singapore" },
            { id: "E002", name: "Kpop Stars Live", date: "2025-06-15", venue: "Marina Bay Sands Expo" }
        ];
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
