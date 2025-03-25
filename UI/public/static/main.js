const homeApp = Vue.createApp({
    data() {
        return { 
            events: [],
            loading: true,
            error: null,
            showModal: false,
            currentImage: '',
            currentEventName: ''
        };
    },
    async created() {
        console.log("Vue App is created. Fetching events...");
        try {
            this.events = await fetchEvents();
            console.log("Events fetched:", this.events);
        } catch (error) {
            console.error("Error in created hook:", error);
            this.error = "Failed to load events. Please try again later.";
        } finally {
            this.loading = false;
        }
    },
    methods: {
        openImageModal(event) {
            if (event.imageBase64) {
                this.currentImage = event.imageBase64;
                this.currentEventName = event.name;
                this.showModal = true;
                
                // Prevent scrolling on the body when modal is open
                document.body.style.overflow = 'hidden';
                
                // Also close modal when user clicks anywhere outside the image
                document.addEventListener('click', this.handleOutsideClick);
                
                // Allow closing with Escape key
                document.addEventListener('keydown', this.handleKeyPress);
            }
        },
        closeImageModal() {
            this.showModal = false;
            this.currentImage = '';
            this.currentEventName = '';
            
            // Re-enable scrolling
            document.body.style.overflow = 'auto';
            
            // Remove event listeners
            document.removeEventListener('click', this.handleOutsideClick);
            document.removeEventListener('keydown', this.handleKeyPress);
        },
        handleOutsideClick(e) {
            // Check if click is on the modal background (not the image)
            if (e.target.classList.contains('image-modal')) {
                this.closeImageModal();
            }
        },
        handleKeyPress(e) {
            // Close modal on Escape key
            if (e.key === 'Escape') {
                this.closeImageModal();
            }
        }
    }
}).mount("#home");

const buyTicketApp = Vue.createApp({
    data() {
        return { tickets: [], message: "" };
    },
    async created() {
        this.tickets = await fetchAvailableTickets();
    },
    methods: {
        async buyTicket(ticketID) {
            this.message = await buyTicketAPI(ticketID);
        }
    }
}).mount("#buyTicket");

const resaleApp = Vue.createApp({
    data() {
        return { ticketID: "", resaleTicketID: "", price: "", message: "" };
    },
    methods: {
        async buyResaleTicket() {
            this.message = await buyResaleAPI(this.ticketID);
        },
        async resellTicket() {
            this.message = await resellTicketAPI(this.resaleTicketID, this.price);
        }
    }
}).mount("#resale");

const checkinApp = Vue.createApp({
    data() {
        return { ticketID: "", message: "" };
    },
    methods: {
        async checkIn() {
            this.message = await checkInAPI(this.ticketID);
        }
    }
}).mount("#checkin");
