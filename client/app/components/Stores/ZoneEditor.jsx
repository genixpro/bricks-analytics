import React from 'react';
import { Grid, Popover, Row, Col, Panel, Button, FormControl, FormGroup, InputGroup, DropdownButton, MenuItem, Tab, Tabs, Nav, NavItem } from 'react-bootstrap';
import Select from 'react-select'
import 'react-select/dist/react-select.css'

class ZoneEditor extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            isDraggingZone: false,
            isEditingZone: false
        }
    }

    componentDidMount()
    {

    }


    /**
     * Triggered when this component is being removed from the screen
     */
    componentWillUnmount()
    {

    }

    onMouseDown(evt)
    {
        if (!this.state.isEditingZone)
        {
            // Start a new rectangle
            this.setState({
                isDraggingZone: true,
                isEditingZone: false,
                startX: evt.nativeEvent.offsetX,
                startY: evt.nativeEvent.offsetY,
                dragX: evt.nativeEvent.offsetX,
                dragY: evt.nativeEvent.offsetY
            }, this.computeZoneCoordinates.bind(this));
        }
        else {
            this.setState({
                isDraggingZone: false,
                isEditingZone: false
            }, this.computeZoneCoordinates.bind(this))
        }
    }

    onMouseMove(evt)
    {
        if (this.state.isDraggingZone && !this.state.isEditingZone) {
            // Start a new rectangle
            this.setState({
                dragX: evt.nativeEvent.offsetX,
                dragY: evt.nativeEvent.offsetY
            }, this.computeZoneCoordinates.bind(this));
        }
    }


    onMouseUp(evt)
    {
        if (this.state.isDraggingZone && !this.state.isEditingZone) {
            // Start a new rectangle
            this.setState({
                isDraggingZone: false,
                isEditingZone: true,
                dragX: evt.nativeEvent.offsetX,
                dragY: evt.nativeEvent.offsetY,
                editorX: evt.nativeEvent.offsetX,
                editorY: evt.nativeEvent.offsetY
            }, this.computeZoneCoordinates.bind(this))
        }
    }


    computeZoneCoordinates()
    {
        const width = Math.abs(this.state.startX - this.state.dragX);
        const height = Math.abs(this.state.startY - this.state.dragY);
        const left = Math.min(this.state.startX, this.state.dragX);
        const top = Math.min(this.state.startY, this.state.dragY);

        this.setState({zone: {left, top, width, height}});
    }


    onChangeZoneType(newType)
    {
        this.setState({
            zoneType: newType,
            isEditingZone: false
        })
    }


    preventEventHandler(e)
    {
        e.preventDefault();
    }

    render()
    {
        const options = [
            { value: 'chocolate', label: 'Chocolate' },
            { value: 'strawberry', label: 'Strawberry' },
            { value: 'vanilla', label: 'Vanilla' }
        ];

        return <div className="zone-editor">
                    <div
                        onMouseDown={this.onMouseDown.bind(this)}
                        onMouseUp={this.onMouseUp.bind(this)}
                        onMouseMove={this.onMouseMove.bind(this)} >
                        <img src={this.props.src} draggable={false}/>
                    </div>
                    {
                        this.state.isDraggingZone ?
                            <div className="zone-overlay" style={{"left": this.state.zone.left, "top": this.state.zone.top, "height": this.state.zone.height, "width": this.state.zone.width}} />
                            : null
                    }
                    {
                        this.state.isEditingZone ?
                            <Popover
                                id="popover-basic"
                                placement="right"
                                positionLeft={this.state.editorX}
                                positionTop={this.state.editorY - 48}
                                title="Popover right">
                                <Select
                                    options={options}
                                    value={this.state.zoneType}
                                    onChange={this.onChangeZoneType.bind(this)}
                                />
                            </Popover>
                        : null
                    }
               </div>;
    }
}

export default ZoneEditor


