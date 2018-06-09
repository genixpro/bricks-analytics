import React from 'react';
import axios from 'axios';
import {withRouter} from "react-router-dom";
import { Grid, Row, Col, Panel, Button, FormControl, FormGroup, InputGroup, DropdownButton, MenuItem, Tab, Tabs, Nav, NavItem } from 'react-bootstrap';
import ZoneEditor from './ZoneEditor';
import _ from 'underscore';


class RealtimeStoreView extends React.Component {
    constructor(props) {
        super(props);

        this.state = {};
    }

    componentDidMount()
    {
        var headers = {durable: false, "auto-delete": false, exclusive: false};
        this.storeSubscription = this.props.messagingClient.subscribe("/exchange/store-time-series-frames-" + this.props.store._id, (message) =>
        {
            const body = JSON.parse(message.body);

            this.setState({frame: body});
        }, headers);
    }


    /**
     * Triggered when this component is being removed from the screen
     */
    componentWillUnmount()
    {
        if (this.storeSubscription)
        {
            this.storeSubscription.unsubscribe();
        }
    }


    render() {
        return (
            <div className={"realtime-store-view"}>
                <br/>
                <Panel>
                    <Row>
                        <Col xs={12}>
                            <h2>Realtime Store View</h2>
                            <div className="storeMap">
                                <img className='store-image' src={'http://localhost:1806/store/' + this.props.match.params.storeId + "/store_layout"} />
                                {this.state.frame &&
                                    this.state.frame.people.map((person) =>
                                    <div
                                        key={person.visitorId}
                                        className={"person-location-box"}
                                         style={{
                                             "left": "calc(" + (person["x"] * 100) + "% - 30px)",
                                             "top": "calc(" + (person["y"] * 100) + "% - 30px)"
                                         }}>
                                        <div className={"person-image-wrapper"}>
                                            <img className="person-image"
                                                 src='/img/person.png'
                                            />
                                        </div>
                                        <div className={"visitor-id-block"}>
                                            <span>Visitor {person.visitorId}</span>
                                        </div>
                                    </div>
                                )
                                }
                            </div>
                        </Col>
                    </Row>
                </Panel>
            </div>
        );
    }
}

export default withRouter(RealtimeStoreView);


