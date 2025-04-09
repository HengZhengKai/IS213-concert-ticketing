const sellTicketServiceBaseUrl = 'http://localhost:5101'; // Port for sell_ticket composite service
const ticketServiceBaseUrl = 'http://localhost:5004'; // Port for ticket service

const app = Vue.createApp({
    data() {
        return {
            // Data for listing tickets
            tickets: [],              // Array to hold user's fetched tickets
            loading: true,          // Loading state indicator
            error: null,            // Error message holder
            user: null,             // Store logged in user info
            token: null,            // Store auth token
            resalePrices: {},       // Object to store resale price input, keyed by ticketID
            resaleMessages: {},     // Object to store feedback per ticket, keyed by ticketID
            
            // Data for buying tickets - RE-ADDING THESE
            resaleTicketsAvailable: [], // Array for tickets available for purchase
            loadingResale: true,        // Loading state for buyer section
            resaleError: null           // Error message for buyer section
            
            // Removed old single form data
            // sellTicketData: {
            //     ticketID: '',
            //     price: null
            // },
            // sellerMessage: '',      
            // sellerMessageType: 'info' 
        };
    },
    async mounted() {
        console.log("[Resale App] Mounted. Checking session and loading tickets...");
        if (typeof SessionManager === 'undefined' || !SessionManager.isLoggedIn()) {
            console.error("[Resale App] SessionManager not defined or user not logged in. Redirecting...");
            window.location.href = 'login.html';
            return;
        }
        this.user = SessionManager.getUserSession();
        this.token = localStorage.getItem('token');

        if (!this.user || !this.token) {
            console.error("[Resale App] User/Token missing. Redirecting...");
            SessionManager.clearSession();
            window.location.href = 'login.html';
            return;
        }
        await this.loadUserTickets();
        await this.loadResaleTickets();
    },
    methods: {
        // Method to fetch user's tickets (similar to check_in_vue.js)
        async loadUserTickets() {
            console.log(`[Resale App] Fetching tickets for userID: ${this.user.userID}`);
            this.loading = true;
            this.error = null;
            try {
                const response = await fetch(`${ticketServiceBaseUrl}/tickets/${this.user.userID}`, {
                    method: 'GET',
                    headers: { 'Authorization': `Bearer ${this.token}`, 'Accept': 'application/json' }
                });
                if (!response.ok) { throw new Error(`HTTP error ${response.status}`); }
                const data = await response.json();
                console.log("[Resale App] Tickets API response:", data);
                let ticketsArray = [];
                if (data && Array.isArray(data.tickets)) { ticketsArray = data.tickets; }
                else if (data && data.data && Array.isArray(data.data.tickets)) { ticketsArray = data.data.tickets; }
                else if (data && data.data && Array.isArray(data.data)) { ticketsArray = data.data; }
                else if (Array.isArray(data)) { ticketsArray = data; }
                else { console.error("[Resale App] Could not find tickets array:", data); }
                
                this.tickets = ticketsArray.map(ticket => ({ // Map to consistent fields
                    ticketID: ticket.ticketID || ticket.ticket_id || null,
                    eventName: ticket.eventName || ticket.event_name || 'Unknown Event',
                    eventDateTime: ticket.eventDateTime || ticket.event_date_time || ticket.date || null,
                    seatNo: ticket.seatNo || ticket.seatNumber || ticket.seat_number || 'N/A',
                    seatCategory: ticket.seatCategory || 'N/A',
                    price: ticket.price, // Original price
                    status: ticket.status,
                    isCheckedIn: ticket.isCheckedIn === true || ticket.is_checked_in === true || ticket.checkedIn === true
                }));

                // Initialize resalePrices structure
                this.tickets.forEach(t => {
                    if (t.ticketID) this.resalePrices[t.ticketID] = null; // Set initial price input to empty
                });

            } catch (error) {
                console.error('[Resale App] Error loading tickets:', error);
                this.error = `Failed to load tickets: ${error.message}.`;
            } finally {
                this.loading = false;
            }
        },
        
        // Method called when listing a specific ticket for resale
        async listTicketForResale(ticketID) {
            const price = parseFloat(this.resalePrices[ticketID]);
            console.log(`[Resale App] Attempting to list ticket ${ticketID} for resale price: ${price}`);
            this.resaleMessages[ticketID] = { type: 'info', text: 'Processing...' }; // Show processing message for this ticket

            // Frontend validation
            if (isNaN(price) || price < 0) {
                this.resaleMessages[ticketID] = { type: 'danger', text: 'Please enter a valid, non-negative resale price.' };
                return;
            }
            if (!this.token) { // Redundant check, but safe
                 this.resaleMessages[ticketID] = { type: 'danger', text: 'Authentication error. Please log in again.' };
                return;
            }

            try {
                // Call Backend API [POST] /sellticket/{ticketID}
                const response = await fetch(`${sellTicketServiceBaseUrl}/sellticket/${ticketID}`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${this.token}`,
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify({ resalePrice: price })
                });

                const data = await response.json();

                if (response.ok) {
                    console.log(`[Resale App] Ticket ${ticketID} listed successfully:`, data);
                    this.resaleMessages[ticketID] = { type: 'success', text: data.message || 'Ticket listed for resale!' };
                    // Optionally refresh tickets or update status locally
                    await this.loadUserTickets(); // Refresh the list to show updated status
                } else {
                    console.error(`[Resale App] Failed to list ticket ${ticketID}:`, data);
                    this.resaleMessages[ticketID] = { type: 'danger', text: `Error (${response.status}): ${data.message || 'Could not list ticket.'}` };
                }
            } catch (error) {
                console.error(`[Resale App] Network error listing ticket ${ticketID}:`, error);
                 this.resaleMessages[ticketID] = { type: 'danger', text: `Error: ${error.message}.` };
            }
        },

        formatDateTime(dateTimeString) {
             if (!dateTimeString) return 'No Date';
            try {
                return new Date(dateTimeString).toLocaleString('en-SG', { 
                    year: 'numeric', month: 'numeric', day: 'numeric', 
                    hour: 'numeric', minute: 'numeric', hour12: true 
                });
            } catch (e) { return 'Invalid Date'; }
        },

        // --- Buyer Methods --- 
        async loadResaleTickets() {
            console.log("[Resale App] Fetching available resale tickets...");
            this.loadingResale = true;
            this.resaleError = null;
            try {
                // Fetch tickets with status 'available'
                const response = await fetch(`${ticketServiceBaseUrl}/tickets/resale`, {
                    method: 'GET',
                    headers: { 'Accept': 'application/json' } // No auth needed to view
                });
                if (!response.ok) { 
                    throw new Error(`HTTP error ${response.status}`); 
                }
                const data = await response.json();
                console.log("[Resale App] Resale Tickets API response:", data);
                
                if (data.code === 200 && data.data && Array.isArray(data.data.tickets)) {
                     // Map to consistent fields (similar to loadUserTickets)
                    this.resaleTicketsAvailable = data.data.tickets.map(ticket => ({ 
                        ticketID: ticket.ticketID || ticket.ticket_id || null,
                        eventName: ticket.eventName || ticket.event_name || 'Unknown Event',
                        eventDateTime: ticket.eventDateTime || ticket.event_date_time || ticket.date || null,
                        seatNo: ticket.seatNo || ticket.seatNumber || ticket.seat_number || 'N/A',
                        seatCategory: ticket.seatCategory || 'N/A',
                        price: ticket.price, // Original price
                        resalePrice: ticket.resalePrice, // Resale price!
                        status: ticket.status, 
                        ownerID: ticket.ownerID // Needed later for purchase logic maybe
                        // Don't need isCheckedIn here
                    }));
                } else {
                     console.error("[Resale App] Could not parse resale tickets array:", data);
                     this.resaleTicketsAvailable = []; // Ensure it's an empty array on error
                     // Optional: Set resaleError based on data.message if available
                }

            } catch (error) {
                console.error('[Resale App] Error loading resale tickets:', error);
                this.resaleError = `Failed to load resale tickets: ${error.message}.`;
                this.resaleTicketsAvailable = []; // Ensure empty on fetch error
            } finally {
                this.loadingResale = false;
            }
        },
        
        async buyResaleTicket(ticket) {
            console.log(`[Resale App] Initiating purchase for ticket:`, ticket);
            // Add a simple loading/feedback state for the specific button if desired
            
            // --- Step 1: Attempt to reserve the ticket --- 
            try {
                console.log(`[Resale App] Attempting to reserve ticket ${ticket.ticketID} by setting status to 'reserved'.`);
                const reserveResponse = await fetch(`${ticketServiceBaseUrl}/ticket/${ticket.ticketID}`, {
                    method: 'PUT',
                    headers: {
                        'Authorization': `Bearer ${this.token}`, // Assuming reservation requires auth
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify({ status: 'reserved' })
                });

                const reserveData = await reserveResponse.json();

                if (!reserveResponse.ok) {
                    // Handle failed reservation (e.g., 409 Conflict)
                    console.error(`[Resale App] Failed to reserve ticket ${ticket.ticketID}:`, reserveData);
                    alert(`Failed to reserve ticket: ${reserveData.message || 'Another user may have already purchased it.'}`);
                    // Optional: Refresh the list of available resale tickets
                    this.loadResaleTickets(); 
                    return; // Stop the purchase process
                }

                // --- Reservation Successful --- 
                console.log(`[Resale App] Ticket ${ticket.ticketID} reserved successfully.`);
                // Immediately update local status (optional but good for UI feedback)
                const reservedTicketIndex = this.resaleTicketsAvailable.findIndex(t => t.ticketID === ticket.ticketID);
                if (reservedTicketIndex !== -1) {
                    this.resaleTicketsAvailable[reservedTicketIndex].status = 'reserved';
                }
                
                // --- Step 2: Proceed to Payment (Placeholder) --- 
                alert(`Ticket ${ticket.ticketID} reserved! Proceeding to payment for $${ticket.resalePrice}... (Payment Implementation Pending)`);
                // TODO: Initiate Stripe Checkout for ticket.resalePrice
                // TODO: On successful payment, call POST /buyresaleticket/{ticketID} with payment details & userID
                // TODO: If payment fails/is cancelled, maybe PUT status back to 'available'?

            } catch (error) {
                console.error(`[Resale App] Network error reserving ticket ${ticket.ticketID}:`, error);
                alert(`Network error trying to reserve ticket: ${error.message}`);
            }
        }
    }
});

app.mount('#resaleApp'); 