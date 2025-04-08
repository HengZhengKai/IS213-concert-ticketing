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
            resaleMessages: {}      // Object to store feedback per ticket, keyed by ticketID
            
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
    },
    computed: {
        // Filter tickets that can potentially be resold 
        // (Adjust logic based on your status field and rules)
        resellableTickets() {
            return this.tickets.filter(t => !t.isCheckedIn && t.status !== 'resale'); // Example filter
        }
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
        }
    }
});

app.mount('#resaleApp'); 