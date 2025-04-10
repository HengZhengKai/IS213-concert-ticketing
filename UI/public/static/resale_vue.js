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
                    if (t.ticketID) this.resalePrices[t.ticketID] = t.price; // Set initial price to original ticket price
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
            const ticket = this.tickets?.find(t => t.ticketID === ticketID);
            console.log('[Resale App] Found ticket:', ticket); // Log the entire ticket object

            if (!ticket) {
                console.error(`[Resale App] Could not find ticket with ID ${ticketID}`);
                this.resaleMessages[ticketID] = { type: 'danger', text: 'Could not find ticket details. Please refresh and try again.' };
                return;
            }

            const price = ticket.price;
            console.log('[Resale App] Original ticket price:', price); // Log the price specifically

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
                console.log(`[Resale App] Making request to: ${sellTicketServiceBaseUrl}/sellticket/${ticketID}`);
                console.log('[Resale App] Request payload:', { resalePrice: price });

                const response = await fetch(`${sellTicketServiceBaseUrl}/sellticket/${ticketID}`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${this.token}`,
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'Origin': window.location.origin
                    },
                    body: JSON.stringify({ resalePrice: price })
                });

                // Log response details
                console.log(`[Resale App] Response status:`, response.status);
                console.log(`[Resale App] Response headers:`, Object.fromEntries([...response.headers.entries()]));

                if (!response.ok) {
                    const errorText = await response.text();
                    console.error(`[Resale App] Error details:`, {
                        endpoint: `${sellTicketServiceBaseUrl}/sellticket/${ticketID}`,
                        status: response.status,
                        statusText: response.statusText,
                        headers: Object.fromEntries([...response.headers.entries()]),
                        error: errorText
                    });

                    // Handle specific error cases
                    switch (response.status) {
                        case 400:
                            throw new Error(`Invalid request: ${errorText}`);
                        case 401:
                            throw new Error('Authentication failed. Please log in again.');
                        case 403:
                            throw new Error('You do not have permission to list this ticket.');
                        case 404:
                            throw new Error('Ticket not found.');
                        case 409:
                            throw new Error('Ticket cannot be listed. It may already be listed or sold.');
                        case 500:
                            throw new Error(`Server error: ${errorText}`);
                        default:
                            throw new Error(`Unexpected error (${response.status}): ${errorText}`);
                    }
                }

                const data = await response.json();
                console.log(`[Resale App] Success response:`, data);

                if (response.ok) {
                    console.log(`[Resale App] Ticket ${ticketID} listed successfully:`, data);
                    this.resaleMessages[ticketID] = { type: 'success', text: data.message || 'Ticket listed for resale!' };
                    await this.loadUserTickets();
                }
            } catch (error) {
                console.error(`[Resale App] Error listing ticket ${ticketID}:`, error);
                
                // Network/Connection errors
                if (error.message.includes('Failed to fetch')) {
                    this.resaleMessages[ticketID] = { 
                        type: 'danger', 
                        text: `Connection error: Could not reach the sell ticket service (${sellTicketServiceBaseUrl}). Please ensure:
                               1. The service is running on port 5101
                               2. You have network connectivity
                               3. CORS is properly configured` 
                    };
                }
                // Authentication errors
                else if (error.message.includes('Authentication failed')) {
                    this.resaleMessages[ticketID] = { 
                        type: 'danger', 
                        text: 'Your session has expired. Please log in again.' 
                    };
                    // Optionally redirect to login
                    // window.location.href = 'login.html';
                }
                // Permission errors
                else if (error.message.includes('permission')) {
                    this.resaleMessages[ticketID] = { 
                        type: 'danger', 
                        text: 'You do not have permission to list this ticket.' 
                    };
                }
                // Ticket state errors
                else if (error.message.includes('already')) {
                    this.resaleMessages[ticketID] = { 
                        type: 'danger', 
                        text: 'This ticket is already listed or has been sold.' 
                    };
                }
                // All other errors
                else {
                    this.resaleMessages[ticketID] = { 
                        type: 'danger', 
                        text: `Error: ${error.message}` 
                    };
                }
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
            
            try {
                // Step 1: Start Stripe Checkout through payment service
                const response = await fetch('http://localhost:5007/start-checkout', {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        mode: 'payment',
                        success_url: `${window.location.origin}/buy_success.html?ticketID=${ticket.ticketID}&userID=${this.user.userID}&session_id={CHECKOUT_SESSION_ID}`,
                        cancel_url: `${window.location.href}`,
                        currency: 'sgd',
                        product_name: `Resale Ticket - ${ticket.eventName} (${ticket.seatNo})`,
                        unit_amount: Math.round(ticket.resalePrice * 100),
                        quantity: 1
                    })
                });

                if (!response.ok) {
                    throw new Error(`HTTP error ${response.status}`);
                }

                const data = await response.json();
                
                // Step 2: Redirect to Stripe Checkout
                if (data.checkout_url) {
                    window.location.href = data.checkout_url;
                } else {
                    throw new Error('No checkout URL received');
                }

            } catch (error) {
                console.error(`[Resale App] Error initiating checkout:`, error);
                alert(`Failed to initiate checkout: ${error.message}`);
            }
        }
    }
});

app.mount('#resaleApp'); 