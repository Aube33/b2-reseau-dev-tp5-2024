const exampleSocket = new WebSocket("ws://localhost:8765");

exampleSocket.onopen = (event) => {
    const input = prompt('Type here');
    exampleSocket.send(input);
};

exampleSocket.onmessage = (event) => {
    console.log("Message from server: " + event.data);
    alert(event.data);
};